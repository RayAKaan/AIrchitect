#!/usr/bin/env python3
"""Run a real geometry/export smoke test against the configured CAD worker.

Run from the repository root after provisioning the worker virtualenv and native
CAD tools. This deliberately does not use the fake worker used by unit tests.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.domains.cad.capability import probe_capabilities  # noqa: E402
from app.domains.cad.config import CadConfig  # noqa: E402
from app.domains.cad.protocol import CadJobOptions, CadJobRequest, Footprint, MassingElement  # noqa: E402
from app.domains.cad.runner import run_cad_job  # noqa: E402


def _close(actual: float, expected: float, tolerance: float = 0.005) -> bool:
    return math.isclose(actual, expected, rel_tol=tolerance, abs_tol=0.001)


def run_smoke(*, require_ifc: bool = False, require_freecad: bool = False) -> dict[str, object]:
    config = CadConfig.from_settings()
    capabilities = probe_capabilities(config, use_cache=False)

    if not capabilities.can_build_geometry:
        raise RuntimeError(
            "No usable solid kernel is available. Worker probe: "
            + json.dumps(capabilities.model_dump(mode="json"), sort_keys=True)
        )
    if require_ifc and not capabilities.ifc.available:
        raise RuntimeError(f"IFC was required but unavailable: {capabilities.ifc.error}")
    if require_freecad and not capabilities.freecad.available:
        raise RuntimeError(f"FreeCAD was required but unavailable: {capabilities.freecad.error}")

    provider = capabilities.select_provider(config.provider)
    request = CadJobRequest(
        job_id="phase22-native-smoke",
        project_name="AIrchitect Phase 22 CAD Smoke",
        elements=[
            MassingElement(
                id="smoke-prism",
                kind="building_mass",
                name="Known 10x8x3.5 m prism",
                footprint=Footprint(points=[(0, 0), (10, 0), (10, 8), (0, 8)]),
                base_elevation_m=0,
                height_m=3.5,
            )
        ],
        options=CadJobOptions(
            write_fcstd=False,
            write_step=True,
            write_ifc=capabilities.ifc.available,
            write_glb=True,
            run_validation=True,
            ifc_schema="IFC4",
        ),
    )
    result = run_cad_job(request, config, capabilities=capabilities, provider=provider)
    if len(result.measurements) != 1:
        raise RuntimeError(f"Expected one solid measurement, got {len(result.measurements)}")
    measured = result.measurements[0]
    checks = {
        "solid_is_valid": measured.is_valid,
        "solid_is_closed": measured.is_closed,
        "solid_count_is_one": measured.solid_count == 1,
        "volume_matches_280_m3": _close(measured.volume_m3, 280.0),
        "surface_area_matches_286_m2": _close(measured.surface_area_m2, 286.0),
        "bounding_x_matches_10_m": _close(measured.bounding_box.size[0], 10.0),
        "bounding_y_matches_8_m": _close(measured.bounding_box.size[1], 8.0),
        "bounding_z_matches_3_5_m": _close(measured.bounding_box.size[2], 3.5),
    }
    if not all(checks.values()):
        raise RuntimeError("Analytical geometry check failed: " + json.dumps(checks, sort_keys=True))

    artifacts = {artifact.kind: artifact for artifact in result.artifacts}
    required_kinds = {"step", "glb"}
    if capabilities.ifc.available or require_ifc:
        required_kinds.add("ifc")
    missing = sorted(kind for kind in required_kinds if kind not in artifacts)
    if missing:
        raise RuntimeError(f"CAD worker omitted required smoke artifacts: {missing}")
    artifact_summary = {}
    for kind, artifact in sorted(artifacts.items()):
        if artifact.byte_size <= 0 or len(artifact.sha256) != 64:
            raise RuntimeError(f"Invalid artifact metadata for {kind}")
        artifact_summary[kind] = {
            "filename": artifact.filename,
            "byte_size": artifact.byte_size,
            "sha256": artifact.sha256,
            "content_type": artifact.content_type,
        }

    return {
        "status": "PASS",
        "provider": result.provider.model_dump(mode="json"),
        "capabilities": {
            "occt_available": capabilities.occt.available,
            "ifc_available": capabilities.ifc.available,
            "freecad_available": capabilities.freecad.available,
        },
        "measurements": {
            "volume_m3": measured.volume_m3,
            "surface_area_m2": measured.surface_area_m2,
            "bounding_box_size_m": list(measured.bounding_box.size),
            "solid_count": measured.solid_count,
            "face_count": measured.face_count,
            "edge_count": measured.edge_count,
            "is_valid": measured.is_valid,
            "is_closed": measured.is_closed,
        },
        "checks": checks,
        "artifacts": artifact_summary,
        "warnings": result.warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-ifc", action="store_true", help="fail unless IFC export is available and succeeds")
    parser.add_argument("--require-freecad", action="store_true", help="fail unless FreeCAD is available")
    args = parser.parse_args()
    try:
        report = run_smoke(require_ifc=args.require_ifc, require_freecad=args.require_freecad)
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
