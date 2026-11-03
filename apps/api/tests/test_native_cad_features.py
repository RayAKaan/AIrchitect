from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "apps/api/app/cad_worker/freecad_script.py"


def test_freecad_worker_script_is_valid_python_and_creates_native_parametric_features():
    source = SCRIPT.read_text(encoding="utf-8")
    ast.parse(source)

    assert 'document.addObject("Part::Box", object_name)' in source
    assert 'document.addObject("Part::Extrusion", object_name)' in source
    assert 'extrusion.DirMode = "Custom"' in source
    assert "extrusion.LengthFwd = height" in source
    assert 'document.addObject("Part::Feature", object_name + "_Profile")' in source
    assert 'document.addObject("Part::Feature", element["id"])' not in source


def test_native_features_retain_canonical_identity_and_metric_provenance():
    source = SCRIPT.read_text(encoding="utf-8")
    for property_name in (
        "CanonicalElementId",
        "CanonicalElementType",
        "SourceWorldModelHash",
        "SemanticModelHash",
        "CoordinateSystem",
        "Units",
        "MaterialClass",
        "BaseElevationM",
        "HeightM",
    ):
        assert property_name in source
