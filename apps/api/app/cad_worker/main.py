"""CAD worker entry point.

Run as::

    <worker-python> -m app.cad_worker.main REQUEST.json RESPONSE.json [--provider occt|freecad]
    <worker-python> -m app.cad_worker.main --capabilities

The API invokes this as a bounded subprocess. It never imports this package
itself, and this package never imports the API. The only channel between them is
the request/response JSON files named on the command line.

Two providers are available and, importantly, they are **not** interchangeable
fallbacks -- they are independent implementations that cross-check each other:

``occt``
    Builds, measures, tessellates and exports using the standalone
    ``cadquery-ocp`` / OCCT 7.9.3 kernel in the worker virtualenv. Also writes the
    IFC via IfcOpenShell.

``freecad``
    Delegates solid construction, measurement, the native ``.FCStd`` document and
    STEP export to ``freecadcmd.exe`` (OCCT 7.8.1). The IFC and GLB are still
    produced by the worker's own OCCT kernel.

When both are available the API runs the job through both and compares the
measured volumes. Two independent B-rep kernels agreeing on a building's volume
to within tolerance is materially stronger evidence of a real solid than either
kernel's self-report, and a disagreement is surfaced rather than averaged away.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
from typing import Any

from app.cad_worker import geometry as geom
from app.cad_worker import ifc_io
from app.cad_worker.mesh import GlbError, MeshPart, build_glb, parse_glb, validate_glb

#: FreeCAD element colours, as linear-ish RGB triples for the GLB material.
COLOURS: dict[str, tuple[float, float, float]] = {
    "building_mass": (0.78, 0.80, 0.84),
    "floor_plate": (0.42, 0.66, 0.86),
    "core": (0.90, 0.62, 0.28),
    "site_boundary": (0.55, 0.74, 0.52),
}

DEFAULT_COLOUR = (0.80, 0.55, 0.55)

SCHEMA_VERSION = "1.0"

#: Environment variable carrying the request path into the FreeCAD subprocess.
_FREECAD_REQUEST_ENV = "AIRCHITECT_CAD_REQUEST"


class RequestError(ValueError):
    """A request was rejected before any geometry work started."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# --------------------------------------------------------------------------- #
# Request validation
# --------------------------------------------------------------------------- #


def _safe_output_dir(request: dict[str, Any]) -> str:
    """Resolve and sandbox-check the output directory.

    The output directory is the only filesystem location a worker may write to.
    It is resolved and then required to sit inside the configured sandbox root, so
    a job cannot be steered into writing over the application, the toolchain, or
    an arbitrary path on the host. Both sides of the comparison are fully resolved
    first, which defeats ``..`` traversal and symlink indirection.

    The sandbox root itself is allowed, and the API runner relies on that: it makes
    the scratch directory both the sandbox and the output location. Treating
    equality as an escape rejected the runner's own contract, and only a real
    end-to-end run could show it -- every other caller happened to pass a subfolder.
    """
    raw_dir = (request.get("output_dir") or "").strip()
    sandbox = (request.get("sandbox_root") or "").strip()
    if not raw_dir:
        raise RequestError("missing_output_dir", "output_dir is required")
    if not sandbox:
        raise RequestError("missing_sandbox", "sandbox_root is required")

    output = os.path.realpath(os.path.abspath(raw_dir))
    root = os.path.realpath(os.path.abspath(sandbox))
    # Compared case-folded: Windows paths are case-insensitive, so
    # C:\Sandbox and c:\sandbox name the same directory and must not read as an
    # escape. normcase is a no-op on POSIX, where the comparison is already exact.
    folded_output = os.path.normcase(output)
    folded_root = os.path.normcase(root)
    if folded_output != folded_root and not folded_output.startswith(folded_root + os.sep):
        raise RequestError(
            "output_dir_escape",
            f"output_dir {output!r} is outside the sandbox root {root!r}",
        )
    os.makedirs(output, exist_ok=True)
    return output


def _validate_elements(request: dict[str, Any]) -> list[dict[str, Any]]:
    """Check the element list before doing any expensive work."""
    elements = request.get("elements") or []
    if not elements:
        raise RequestError("no_elements", "the request contains no massing elements")
    if len(elements) > 2000:
        raise RequestError("too_many_elements", f"{len(elements)} elements exceeds the limit of 2000")
    seen: set[str] = set()
    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            raise RequestError("bad_element", f"element {index} is not an object")
        element_id = element.get("id")
        if not isinstance(element_id, str) or not element_id:
            raise RequestError("bad_element_id", f"element {index} has no usable id")
        if element_id in seen:
            raise RequestError("duplicate_element_id", f"duplicate element id {element_id!r}")
        seen.add(element_id)
        height = element.get("height_m")
        if not isinstance(height, (int, float)) or not (0 < float(height) <= 1000):
            raise RequestError("bad_height", f"element {element_id!r} has an unusable height {height!r}")
        footprint = element.get("footprint") or {}
        points = footprint.get("points") if isinstance(footprint, dict) else None
        if not isinstance(points, list) or len(points) < 3:
            raise RequestError(
                "bad_footprint", f"element {element_id!r} needs a footprint of at least 3 points"
            )
    return elements


# --------------------------------------------------------------------------- #
# Artifact helpers
# --------------------------------------------------------------------------- #


def _read_artifact(path: str, kind: str) -> dict[str, Any]:
    """Read a produced file into an :class:`ArtifactRef`-shaped dict."""
    content_types = {
        "freecad_document": "application/vnd.freecad",
        "step": "model/step",
        "ifc": "application/x-step",  # placeholder; corrected below
        "glb": "model/gltf-binary",
        "brep": "model/occt-brep",
    }
    if kind == "ifc":
        content_types["ifc"] = "application/x-ifc"
    with open(path, "rb") as handle:
        payload = handle.read()
    return {
        "kind": kind,
        "filename": os.path.basename(path),
        "content_type": content_types.get(kind, "application/octet-stream"),
        "byte_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "payload": base64.b64encode(payload).decode("ascii"),
    }


def _artifacts_from_paths(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert the FreeCAD adapter's path-carrying artifacts into payload form."""
    return [_read_artifact(entry["path"], entry["kind"]) for entry in entries]


# --------------------------------------------------------------------------- #
# OCCT provider
# --------------------------------------------------------------------------- #


def run_occt(request: dict[str, Any], output_dir: str) -> dict[str, Any]:
    """Build, measure, validate, tessellate and export using the OCCT kernel."""
    elements = _validate_elements(request)
    options = request.get("options", {})
    tolerances = request.get("tolerances", {})
    job_id = (request.get("job_id") or "geometry").strip() or "geometry"

    measurements: list[dict[str, Any]] = []
    shapes: list[Any] = []
    mesh_parts: list[MeshPart] = []
    warnings: list[str] = []
    volume_tolerance = float(tolerances.get("volume_tolerance_ratio", 0.005))
    area_tolerance = float(tolerances.get("area_tolerance_ratio", 0.005))

    for element in elements:
        points = [(float(x), float(y)) for x, y in element["footprint"]["points"]]
        height = float(element["height_m"])
        base = float(element.get("base_elevation_m", 0.0))
        kind = element.get("kind", "building_mass")

        shape = geom.build_prism(points, base, height)
        shapes.append(shape)
        measurement = geom.measure(shape, element_id=element["id"], kind=kind)
        measurements.append(measurement)

        analytic_area = abs(geom.signed_area(points))
        analytic_volume = analytic_area * height
        # Closed-form lateral area of a prism: the footprint swept vertically.
        # Volume alone is a weak check -- a solid can enclose the right volume
        # with the wrong faces. Surface area pins the face count and the
        # perimeter independently, so it catches a malformed or mis-swept solid
        # that volume alone would wave through.
        perimeter = geom.perimeter(points)
        analytic_surface_area = 2.0 * analytic_area + perimeter * height
        measurement["analytic_area_m2"] = analytic_area
        measurement["analytic_volume_m3"] = analytic_volume
        measurement["analytic_surface_area_m2"] = analytic_surface_area

        # Cross-check the kernel's answer against the closed-form answer. A
        # disagreement means either the footprint is non-planar/degenerate or the
        # solid is malformed, and in both cases the artifact must not be trusted.
        if analytic_volume > 1e-6:
            error = abs(measurement["volume_m3"] - analytic_volume) / analytic_volume
            measurement["volume_relative_error"] = error
            if error > volume_tolerance:
                warnings.append(
                    f"element {element['id']!r}: measured volume {measurement['volume_m3']:.4f} m3 "
                    f"differs from the closed-form {analytic_volume:.4f} m3 by "
                    f"{error * 100:.3f}% (tolerance {volume_tolerance * 100:.3f}%)"
                )
        if analytic_surface_area > 1e-6:
            area_error = (
                abs(measurement["surface_area_m2"] - analytic_surface_area)
                / analytic_surface_area
            )
            measurement["area_relative_error"] = area_error
            if area_error > area_tolerance:
                warnings.append(
                    f"element {element['id']!r}: measured area "
                    f"{measurement['surface_area_m2']:.4f} m2 differs from the closed-form "
                    f"{analytic_surface_area:.4f} m2 by {area_error * 100:.3f}% "
                    f"(tolerance {area_tolerance * 100:.3f}%)"
                )
        if not measurement["is_valid"]:
            warnings.append(
                f"element {element['id']!r}: OCCT reports the solid as invalid; "
                "the footprint may be self-intersecting or have a zero-thickness edge"
            )

        if options.get("write_glb", True):
            tessellation = geom.tessellate(
                shape,
                linear_deflection_m=float(request.get("mesh_deflection_m", 0.05)),
                angular_deflection_rad=float(request.get("mesh_angular_deflection_rad", 0.35)),
            )
            mesh_parts.append(
                MeshPart(
                    name=element.get("name") or element["id"],
                    vertices=tessellation["vertices"],
                    indices=tessellation["indices"],
                    color=COLOURS.get(kind, DEFAULT_COLOUR),
                )
            )

    artifacts: list[dict[str, Any]] = []
    if shapes:
        combined = geom.fuse(shapes)
        if options.get("write_step", True):
            step_path = os.path.join(output_dir, job_id + ".step")
            geom.export_step(combined, step_path)
            artifacts.append(_read_artifact(step_path, "step"))
        if options.get("write_glb", True) and mesh_parts:
            glb_path = os.path.join(output_dir, job_id + ".glb")
            glb_bytes = build_glb(mesh_parts)
            # Validate before writing: a GLB that fails here is a job error, not
            # a broken artifact for the viewer to trip over later.
            gltf, binary_chunk = parse_glb(glb_bytes)
            validate_glb(gltf, binary_chunk)
            with open(glb_path, "wb") as handle:
                handle.write(glb_bytes)
            artifacts.append(_read_artifact(glb_path, "glb"))

    ifc_summary: dict[str, Any] | None = None
    if options.get("write_ifc", True):
        ifc_path = os.path.join(output_dir, job_id + ".ifc")
        ifc_summary = ifc_io.write_ifc(
            ifc_path,
            project_name=request.get("project_name") or "AIrchitect Project",
            site_name="Site",
            building_name=request.get("project_name") or "AIrchitect Project",
            storey_name="Level_00",
            masses=[
                {
                    "id": element["id"],
                    "name": element.get("name") or element["id"],
                    "footprint": element["footprint"]["points"],
                    "base_elevation_m": element.get("base_elevation_m", 0.0),
                    "height_m": element["height_m"],
                    "material_class": element.get("material_class", "conceptual_mass"),
                }
                for element in elements
            ],
            schema=options.get("ifc_schema", "IFC4"),
            metadata={
                "GeneratedBy": "AIrchitect CAD worker",
                "Provider": "occt",
                "ElementCount": len(elements),
            },
        )
        # Re-open the file we just wrote. An export that cannot be read back is
        # not a successful export.
        ifc_summary["inspection"] = ifc_io.inspect_ifc(ifc_path)
        artifacts.append(_read_artifact(ifc_path, "ifc"))

    kernel = geom.describe_kernel()
    validation = _validate(measurements, options.get("run_validation", True), request)

    return {
        "status": "ok",
        "job_id": job_id,
        "provider": {
            "provider": "occt",
            "engine_name": "OCCT via cadquery-ocp",
            "engine_version": kernel["occt_version"],
            "occt_version": kernel["occt_version"],
            "occt_build": "",
            "python_version": kernel["python_version"],
            "ifc_library_version": ifc_io.library_version(),
            "freecad_version": None,
        },
        "measurements": measurements,
        "combined_volume_m3": sum(m["volume_m3"] for m in measurements),
        "combined_area_m2": sum(m["surface_area_m2"] for m in measurements),
        "combined_bounding_box": _combined_bbox(measurements),
        "artifacts": artifacts,
        "validation": validation,
        "element_count": len(elements),
        "warnings": warnings,
        "ifc_summary": ifc_summary,
    }


def _combined_bbox(measurements: list[dict[str, Any]]) -> dict[str, list[float]] | None:
    """Union the per-element bounding boxes into one site-wide box."""
    if not measurements:
        return None
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for measurement in measurements:
        box = measurement["bounding_box"]
        for axis in range(3):
            lo[axis] = min(lo[axis], float(box["min"][axis]))
            hi[axis] = max(hi[axis], float(box["max"][axis]))
    return {"min": lo, "max": hi}


def _validate(
    measurements: list[dict[str, Any]], enabled: bool, request: dict[str, Any]
) -> dict[str, Any] | None:
    """Check every measured solid against its closed-form expectation."""
    if not enabled:
        return None
    tolerances = request.get("tolerances", {})
    volume_tolerance = float(tolerances.get("volume_tolerance_ratio", 0.005))
    checks: list[dict[str, Any]] = []
    errors: list[str] = []

    for measurement in measurements:
        element_id = measurement["id"]
        for code, passed, actual, expected in (
            (
                "solid_valid",
                bool(measurement["is_valid"]),
                bool(measurement["is_valid"]),
                True,
            ),
            ("solid_closed", bool(measurement["is_closed"]), bool(measurement["is_closed"]), True),
            (
                "single_solid",
                measurement["solid_count"] == 1,
                measurement["solid_count"],
                1,
            ),
            (
                "volume_positive",
                measurement["volume_m3"] > 0,
                measurement["volume_m3"],
                "> 0",
            ),
            (
                "volume_matches_analytic",
                measurement.get("volume_relative_error", 0.0) <= volume_tolerance,
                measurement.get("volume_relative_error"),
                f"<= {volume_tolerance}",
            ),
        ):
            status = "PASS" if passed else "FAIL"
            checks.append(
                {
                    "code": f"{code}",
                    "status": status,
                    "actual": actual,
                    "expected": expected,
                    "detail": element_id,
                    "source": "solid" if code.startswith("solid") else "analytic",
                }
            )
            if not passed:
                errors.append(f"{element_id}:{code}")

    return {
        "valid": not errors,
        "checks": checks,
        "errors": errors,
        "warnings": [],
    }


# --------------------------------------------------------------------------- #
# FreeCAD provider
# --------------------------------------------------------------------------- #


def run_freecad(
    request: dict[str, Any], output_dir: str, freecad_root: str
) -> dict[str, Any]:
    """Delegate solid work to ``freecadcmd.exe``, then finish IFC/GLB with OCCT."""
    _validate_elements(request)
    job_id = (request.get("job_id") or "geometry").strip() or "geometry"

    executable = _find_freecad_cmd(freecad_root)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "freecad_script.py")
    request_path = os.path.join(output_dir, job_id + ".freecad_request.json")
    with open(request_path, "w", encoding="utf-8") as handle:
        json.dump(request, handle)

    timeout = float(request.get("freecad_timeout_seconds", 180.0))
    # The request path is passed by environment variable, not argv. freecadcmd
    # treats *every* positional file argument as a document to open, so
    # "freecadcmd script.py request.json" makes FreeCAD try to import the JSON
    # as a mesh document after the script finishes, which fails with a confusing
    # YAML-mesh traceback. An environment variable sidesteps extension sniffing
    # entirely and keeps the script the only argument FreeCAD sees.
    child_env = dict(os.environ)
    child_env[_FREECAD_REQUEST_ENV] = request_path
    try:
        completed = subprocess.run(
            [executable, script],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=child_env,
        )
    except subprocess.TimeoutExpired as exc:
        raise geom.GeometryError(
            f"FreeCAD exceeded its {timeout:g}s budget and was terminated"
        ) from exc

    payload = _extract_freecad_payload(completed.stdout)
    if payload is None:
        raise geom.GeometryError(
            "FreeCAD produced no result payload; stderr tail: "
            + (completed.stderr or "<empty>")[-500:]
        )
    if payload.get("status") != "ok":
        raise geom.GeometryError(
            f"FreeCAD reported {payload.get('error_code')}: {payload.get('message')}"
        )

    # FreeCAD's own artifacts (native document + STEP), converted to payloads.
    artifacts = _artifacts_from_paths(payload.get("artifacts", []))

    # IFC and GLB remain the worker's responsibility. The request is re-run
    # through the OCCT path with the FreeCAD-only toggles disabled, so the two
    # kernels measure the same design independently.
    occt_request = dict(request)
    occt_request["options"] = {
        **request.get("options", {}),
        "write_fcstd": False,
        "write_step": False,
    }
    occt_result = run_occt(occt_request, output_dir)
    artifacts.extend(occt_result["artifacts"])

    merged = _merge_providers(payload, occt_result)
    merged["artifacts"] = artifacts
    merged["provider"]["freecad_version"] = payload["provider"].get("freecad_version")
    merged["provider"]["occt_version"] = payload["provider"].get("occt_version")
    merged["provider"]["occt_build"] = payload["provider"].get("occt_build", "")
    return merged


def _extract_freecad_payload(stdout: str) -> dict[str, Any] | None:
    """Find the sentinel-prefixed JSON line in FreeCAD's noisy stdout."""
    sentinel = "AI_FREECAD_RESULT:"
    for line in (stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith(sentinel):
            try:
                parsed = json.loads(stripped[len(sentinel) :])
            except json.JSONDecodeError:
                continue
            # The payload must be an object; a bare list or scalar would satisfy
            # the annotation while breaking every caller that indexes it.
            if isinstance(parsed, dict):
                return parsed
    return None


def _find_freecad_cmd(freecad_root: str) -> str:
    """Locate ``freecadcmd.exe`` in either supported portable layout."""
    if not freecad_root:
        raise geom.GeometryError("no FreeCAD root is configured")
    candidates = (
        os.path.join(freecad_root, "bin", "freecadcmd.exe"),
        os.path.join(freecad_root, "freecadcmd.exe"),
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    raise geom.GeometryError(
        f"freecadcmd.exe was not found under {freecad_root}; looked in "
        + " and ".join(candidates)
    )


def _merge_providers(freecad: dict[str, Any], occt: dict[str, Any]) -> dict[str, Any]:
    """Combine two kernels' results and report where they disagree.

    Disagreement is never averaged away. If FreeCAD's OCCT 7.8.1 and the
    standalone OCCT 7.9.3 disagree on a volume by more than the configured
    tolerance, that is a finding the caller must see, so it becomes both a
    warning and a failing validation check.
    """
    warnings = list(freecad.get("warnings", [])) + list(occt.get("warnings", []))
    validation = occt.get("validation")
    tolerance = 0.005

    occt_by_id = {m["id"]: m for m in occt["measurements"]}
    cross_checks: list[dict[str, Any]] = []
    mismatched: list[str] = []

    for measurement in freecad.get("measurements", []):
        element_id = measurement["id"]
        other = occt_by_id.get(element_id)
        if other is None:
            continue
        a = float(measurement["volume_m3"])
        b = float(other["volume_m3"])
        relative = abs(a - b) / b if b > 1e-9 else abs(a - b)
        agreed = relative <= tolerance
        cross_checks.append(
            {
                "code": "kernel_volume_agreement",
                "status": "PASS" if agreed else "FAIL",
                "actual": {"freecad": a, "occt": b},
                "expected": f"within {tolerance * 100:.3f}%",
                "detail": element_id,
                "source": "provider",
            }
        )
        if not agreed:
            mismatched.append(element_id)
            warnings.append(
                f"element {element_id!r}: FreeCAD measured {a:.4f} m3 but OCCT measured "
                f"{b:.4f} m3 ({relative * 100:.3f}% apart); the two kernels disagree"
            )

    if validation is not None and cross_checks:
        validation["checks"].extend(cross_checks)
        validation["errors"].extend(
            f"{check['detail']}:{check['code']}" for check in cross_checks if check["status"] == "FAIL"
        )
        validation["valid"] = not validation["errors"]
        validation["warnings"].extend(mismatched)

    return {
        "status": "ok",
        "job_id": freecad.get("job_id", ""),
        "provider": {
            "provider": "freecad",
            "engine_name": "FreeCAD",
            "engine_version": freecad["provider"].get("engine_version", ""),
            "occt_version": occt["provider"].get("occt_version"),
            "occt_build": "",
            "python_version": freecad["provider"].get("python_version", ""),
            "ifc_library_version": occt["provider"].get("ifc_library_version"),
            "freecad_version": freecad["provider"].get("freecad_version"),
        },
        "measurements": freecad["measurements"],
        "combined_volume_m3": freecad.get("combined_volume_m3", 0.0),
        "combined_area_m2": freecad.get("combined_area_m2", 0.0),
        "combined_bounding_box": freecad.get("combined_bounding_box"),
        "artifacts": [],
        "validation": validation,
        "element_count": freecad.get("element_count", 0),
        "warnings": warnings,
        "cross_validated": True,
    }


# --------------------------------------------------------------------------- #
# Capabilities
# --------------------------------------------------------------------------- #


def probe_capabilities(freecad_root: str = "") -> dict[str, Any]:
    """Report what this interpreter can actually do.

    Returned as data rather than raised as errors so the API can make a single
    informed decision about which provider to use, and so the failure modes stay
    distinguishable in a health endpoint.
    """
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "python_version": ".".join(str(p) for p in sys.version_info[:3]),
        "occt": {"available": False, "error": ""},
        "ifc": {"available": False, "error": "", "version": None},
        "freecad": {"available": False, "error": "", "version": None, "occt_version": None},
        "glb": {"available": True, "error": ""},
    }
    try:
        report["occt"].update(geom.describe_kernel())
        report["occt"]["available"] = True
    except Exception as exc:
        report["occt"]["error"] = f"{type(exc).__name__}: {exc}"[:400]
    try:
        report["ifc"]["version"] = ifc_io.library_version()
        report["ifc"]["available"] = True
    except Exception as exc:
        report["ifc"]["error"] = f"{type(exc).__name__}: {exc}"[:400]
    if freecad_root:
        try:
            executable = _find_freecad_cmd(freecad_root)
            completed = subprocess.run(
                [
                    executable,
                    "-c",
                    "import FreeCAD,Part;print('AI_FREECAD_RESULT:'+FreeCAD.Version()[0]+'.'+"
                    "FreeCAD.Version()[1]+'.'+FreeCAD.Version()[2]+'|'+str(Part.OCC_VERSION))",
                ],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            line = next(
                (
                    candidate.strip()
                    for candidate in (completed.stdout or "").splitlines()
                    if "AI_FREECAD_RESULT:" in candidate
                ),
                "",
            )
            if line:
                version, _, occt = line.split("AI_FREECAD_RESULT:")[1].partition("|")
                report["freecad"].update(
                    {"available": True, "version": version, "occt_version": occt}
                )
            else:
                report["freecad"]["error"] = "FreeCAD did not report a version"
        except Exception as exc:
            report["freecad"]["error"] = f"{type(exc).__name__}: {exc}"[:400]
    return report


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run the requested provider, write the response file."""
    parser = argparse.ArgumentParser(description="AIrchitect CAD worker")
    parser.add_argument("request", nargs="?", help="path to the request JSON")
    parser.add_argument("response", nargs="?", help="path to write the response JSON")
    parser.add_argument(
        "--provider",
        choices=("occt", "freecad"),
        default="occt",
        help="which kernel to build the geometry with",
    )
    parser.add_argument(
        "--freecad-root",
        default=os.environ.get("CAD_FREECAD_ROOT", ""),
        help="root of the FreeCAD portable installation",
    )
    parser.add_argument(
        "--capabilities",
        action="store_true",
        help="print a capability report and exit",
    )
    args = parser.parse_args(argv)

    if args.capabilities:
        print(json.dumps(probe_capabilities(args.freecad_root), sort_keys=True))
        return 0

    if not args.request or not args.response:
        parser.error("both request and response paths are required")

    job_id = ""
    try:
        # utf-8-sig tolerates a byte-order mark. Windows tooling (PowerShell's
        # Out-File/Set-Content, some editors) writes BOMs by default, and a
        # worker that dies on a BOM turns a trivial encoding quirk into a
        # geometry outage.
        with open(args.request, "r", encoding="utf-8-sig") as handle:
            request = json.load(handle)
        job_id = str(request.get("job_id", ""))
        output_dir = _safe_output_dir(request)
        if args.provider == "freecad":
            result = run_freecad(request, output_dir, args.freecad_root)
        else:
            result = run_occt(request, output_dir)
    except RequestError as exc:
        _write_response(
            args.response,
            {
                "schema_version": SCHEMA_VERSION,
                "job_id": job_id,
                "status": "error",
                "error_code": exc.code,
                "message": exc.message,
                "detail": "",
                "provider": args.provider,
            },
        )
        return 2
    except Exception as exc:
        _write_response(
            args.response,
            {
                "schema_version": SCHEMA_VERSION,
                "job_id": job_id,
                "status": "error",
                "error_code": type(exc).__name__,
                "message": str(exc)[:2000],
                "detail": "",
                "provider": args.provider,
            },
        )
        return 1

    result["schema_version"] = SCHEMA_VERSION
    _write_response(args.response, result)
    return 0


def _write_response(path: str, payload: dict[str, Any]) -> None:
    """Write the response JSON atomically enough for a single reader."""
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(temporary, path)


if __name__ == "__main__":
    raise SystemExit(main())
