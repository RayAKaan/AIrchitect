"""FreeCAD-side geometry script, executed by ``freecadcmd.exe``.

This file is run as a *script argument* by FreeCAD's console executable, not
imported by the API and not imported by the worker. It therefore has to be
self-contained: it shares no code with the rest of AIrchitect and depends on
nothing outside the standard library plus FreeCAD's own modules.

Two constraints are load-bearing:

* **It must not import ``ifcopenshell``.** FreeCAD 1.1.3 ships a vendored copy
  (0.8.4, LGPL-3.0) which we deliberately do not use, because the pinned
  0.8.5 in the worker venv is the single supported IFC implementation.
  ``test_freecad_adapter.py`` asserts the import never appears here.
* **It must never be built from user input.** The script path is fixed; the
  request arrives as a file path in ``AIRCHITECT_CAD_REQUEST``. Job content
  arrives as JSON data, so there is no path in which user data becomes Python
  source.

FreeCAD prints banners and progress noise to both streams, so machine-readable
output is emitted as a single sentinel-prefixed line and everything else is
ignored by the caller.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

RESULT_SENTINEL = "AI_FREECAD_RESULT:"

#: Refuse to emit an artifact larger than this. A degenerate profile with a huge
#: tessellation can otherwise fill the disk.
MAX_ARTIFACT_BYTES = 256 * 1024 * 1024


def _shoelace(points):
    """Return the signed area of a closed 2D ring."""
    total = 0.0
    count = len(points)
    for index in range(count):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % count]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def _count(shape, kind):
    """Count sub-shapes of *kind* within *shape*."""
    count = 0
    for item in shape.SubShapes:
        if item.ShapeType == kind:
            count += 1
    return count


def _recount(shape, kind):
    """Recursively count sub-shapes of *kind* within *shape*."""
    total = 0
    if shape.ShapeType == kind:
        total += 1
    for child in shape.SubShapes:
        total += _recount(child, kind)
    return total


def build_prism(footprint, base_elevation_m, height_m):
    """Extrude a footprint ring upward into a solid, returning a Part shape."""
    import FreeCAD
    import Part

    points = [(float(x), float(y)) for x, y in footprint]
    if _shoelace(points) < 0:
        points.reverse()
    # FreeCAD.Vector, not Part.Vector: in FreeCAD 1.1.3 the Part module does not
    # re-export Vector, so Part.Vector raises AttributeError.
    vectors = [FreeCAD.Vector(x, y, 0.0) for x, y in points]
    wire = Part.makePolygon(vectors + [vectors[0]])
    face = Part.Face(wire)
    if not face.isValid():
        raise ValueError("footprint did not produce a valid planar face")
    solid = face.extrude(FreeCAD.Vector(0.0, 0.0, float(height_m)))
    if base_elevation_m:
        solid.translate(FreeCAD.Vector(0.0, 0.0, float(base_elevation_m)))
    return solid


def measure(shape, element_id, kind):
    """Measure a real solid and return verified quantities."""
    box = shape.BoundBox
    volume = float(shape.Volume)
    return {
        "id": element_id,
        "kind": kind,
        "volume_m3": volume,
        "surface_area_m2": float(shape.Area),
        "centroid": [float(shape.CenterOfMass.x), float(shape.CenterOfMass.y), float(shape.CenterOfMass.z)],
        "center_of_mass": [
            float(shape.CenterOfMass.x),
            float(shape.CenterOfMass.y),
            float(shape.CenterOfMass.z),
        ],
        "bounding_box": {
            "min": [float(box.XMin), float(box.YMin), float(box.ZMin)],
            "max": [float(box.XMax), float(box.YMax), float(box.ZMax)],
        },
        "solid_count": _recount(shape, "Solid"),
        "face_count": _recount(shape, "Face"),
        "edge_count": _recount(shape, "Edge"),
        "vertex_count": _recount(shape, "Vertex"),
        "is_valid": bool(shape.isValid()),
        "is_closed": bool(shape.isClosed()),
    }


def _sha256(path):
    """Return the hex SHA-256 of a file, read in chunks."""
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(request_path):
    """Build every requested mass in FreeCAD, write artifacts, return a result."""
    import FreeCAD
    import Part

    with open(request_path, "r", encoding="utf-8-sig") as handle:
        request = json.load(handle)

    output_dir = request["output_dir"]
    os.makedirs(output_dir, exist_ok=True)

    options = request.get("options", {})
    job_id = request.get("job_id", "") or "geometry"
    elements = request.get("elements", [])

    document = FreeCAD.newDocument("AIrchitect_" + job_id)
    measurements = []
    warnings = []
    solids = []

    for element in elements:
        shape = build_prism(
            element["footprint"]["points"],
            element.get("base_elevation_m", 0.0),
            element["height_m"],
        )
        measurement = measure(shape, element["id"], element.get("kind", "building_mass"))
        measurements.append(measurement)
        solids.append(shape)

        # Add to the native document so the .FCStd artifact contains real
        # parametric FreeCAD features, not just a baked mesh.
        feature = document.addObject("Part::Feature", element["id"])
        feature.Shape = shape
        feature.Label = element.get("name") or element["id"]
        if element.get("source_reference"):
            feature.addProperty("App::PropertyString", "SourceReference", "AIrchitect")
            feature.SourceReference = element["source_reference"]

        if not measurement["is_valid"]:
            warnings.append(
                f"element {element['id']} produced an invalid solid; "
                "review its footprint before accepting this alternative"
            )

    document.recompute()

    artifacts = []

    if options.get("write_fcstd", True):
        fcstd_path = os.path.join(output_dir, job_id + ".FCStd")
        document.saveAs(fcstd_path)
        artifacts.append(
            {
                "kind": "freecad_document",
                "filename": os.path.basename(fcstd_path),
                "path": fcstd_path,
            }
        )

    if options.get("write_step", True) and solids:
        step_path = os.path.join(output_dir, job_id + ".step")
        Part.export(solids, step_path)
        artifacts.append(
            {
                "kind": "step",
                "filename": os.path.basename(step_path),
                "path": step_path,
            }
        )

    FreeCAD.closeDocument(document.Name)

    # Fill in sizes and hashes last, once every file is on disk.
    for artifact in artifacts:
        size = os.path.getsize(artifact["path"])
        if size > MAX_ARTIFACT_BYTES:
            raise ValueError(
                f"{artifact['filename']} is {size} bytes, above the {MAX_ARTIFACT_BYTES} byte limit"
            )
        artifact["byte_size"] = size
        artifact["sha256"] = _sha256(artifact["path"])

    combined = Part.makeCompound(solids) if solids else None
    combined_box = None
    combined_volume = 0.0
    combined_area = 0.0
    if combined is not None:
        box = combined.BoundBox
        combined_box = {
            "min": [float(box.XMin), float(box.YMin), float(box.ZMin)],
            "max": [float(box.XMax), float(box.YMax), float(box.ZMax)],
        }
        for measurement in measurements:
            combined_volume += measurement["volume_m3"]
            combined_area += measurement["surface_area_m2"]

    return {
        "status": "ok",
        "job_id": job_id,
        "provider": {
            "provider": "freecad",
            "engine_name": "FreeCAD",
            "engine_version": ".".join(FreeCAD.Version()[:3]),
            "freecad_version": ".".join(FreeCAD.Version()[:3]),
            "occt_version": getattr(Part, "OCC_VERSION", "unknown"),
            "occt_build": FreeCAD.Version()[3] if len(FreeCAD.Version()) > 3 else "",
            "python_version": ".".join(str(p) for p in sys.version_info[:3]),
        },
        "measurements": measurements,
        "combined_volume_m3": combined_volume,
        "combined_area_m2": combined_area,
        "combined_bounding_box": combined_box,
        "artifacts": artifacts,
        "element_count": len(elements),
        "warnings": warnings,
    }


def main():
    """Script entry point: emit exactly one sentinel-prefixed JSON result line."""
    # The worker passes the request path in AIRCHITECT_CAD_REQUEST. argv is kept
    # as a fallback so the script stays runnable by hand during debugging
    # ("freecadcmd freecad_script.py request.json"), but the worker does not rely
    # on it: freecadcmd tries to *import* any non-script file argument, so a JSON
    # path on argv makes FreeCAD crash after the script has succeeded.
    request_path = os.environ.get("AIRCHITECT_CAD_REQUEST")
    if not request_path and len(sys.argv) > 2:
        # argv[0] is the executable and argv[1] is this script, so a manually
        # supplied request is the trailing argument.
        request_path = sys.argv[-1]
    if not request_path:
        print(RESULT_SENTINEL + json.dumps({
            "status": "error",
            "error_code": "missing_request",
            "message": "no request file was supplied",
        }))
        return 1
    try:
        result = run(request_path)
    except Exception as exc:
        print(
            RESULT_SENTINEL
            + json.dumps(
                {
                    "status": "error",
                    "error_code": type(exc).__name__,
                    "message": str(exc),
                    "detail": traceback.format_exc()[-4000:],
                }
            )
        )
        return 1
    print(RESULT_SENTINEL + json.dumps(result))
    return 0


# FreeCAD executes a script argument as a *module*, so __name__ is
# "freecad_script", never "__main__". Guarding on "__main__" therefore silently
# does nothing and the worker sees no payload at all, so main() is called
# unconditionally.
#
# The return code is deliberately not raised as SystemExit: FreeCAD imports this
# file, and a SystemExit escaping a module import tears down the interpreter
# before buffered stdout is flushed, which loses the payload line entirely. The
# caller judges success by the presence of the sentinel, not the exit code.
_EXIT_CODE = main()

# Belt and braces for the same reason: force the payload out before FreeCAD
# regains control and starts exiting.
sys.stdout.flush()
sys.stderr.flush()
