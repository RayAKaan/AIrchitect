from __future__ import annotations

import hashlib

import pytest

from app.cad_worker.dxf_io import DxfError, validate_dxf, write_footprint_dxf
from app.domains.cad.export_validation import validate_export


def _elements():
    return [
        {
            "id": "wall-1",
            "kind": "wall",
            "base_elevation_m": 0.0,
            "footprint": {"points": [[0, 0], [5, 0], [5, 0.2], [0, 0.2]]},
        },
        {
            "id": "slab-1",
            "kind": "floor_plate",
            "base_elevation_m": -0.25,
            "footprint": {"points": [[0, 0], [5, 0], [5, 4], [0, 4]]},
        },
    ]


def test_dxf_export_is_metric_closed_and_preserves_canonical_identity(tmp_path):
    path = tmp_path / "model.dxf"
    summary = write_footprint_dxf(path, _elements(), source_model_hash="a" * 64)
    data = path.read_bytes()

    assert summary["schema"] == "AC1015"
    assert summary["units"] == "m"
    assert summary["entity_count"] == 2
    assert summary["canonical_element_ids"] == ["slab-1", "wall-1"]
    assert summary["sha256"] == hashlib.sha256(data).hexdigest()
    assert validate_dxf(data, expected_element_ids=("wall-1", "slab-1"))["status"] == "PASS"


def test_dxf_export_rejects_duplicate_and_invalid_geometry(tmp_path):
    duplicate = _elements()
    duplicate[1]["id"] = "wall-1"
    with pytest.raises(DxfError, match="duplicate canonical element ID"):
        write_footprint_dxf(tmp_path / "duplicate.dxf", duplicate)

    invalid = _elements()
    invalid[0]["footprint"]["points"] = [[0, 0], [1, 1]]
    with pytest.raises(DxfError, match="no valid footprint"):
        write_footprint_dxf(tmp_path / "invalid.dxf", invalid)


def test_dxf_validation_rejects_missing_canonical_element_identity(tmp_path):
    path = tmp_path / "model.dxf"
    write_footprint_dxf(path, _elements())
    data = path.read_bytes().replace(b"wall-1", b"other-1")
    with pytest.raises(DxfError, match="canonical element IDs do not match"):
        validate_dxf(data, expected_element_ids=("wall-1", "slab-1"))


def test_cad_export_validator_accepts_dxf_bytes(tmp_path):
    path = tmp_path / "model.dxf"
    summary = write_footprint_dxf(path, _elements())
    data = path.read_bytes()
    result = validate_export(
        "dxf",
        data,
        declared_sha256=summary["sha256"],
        declared_size=len(data),
        declared_content_type="image/vnd.dxf",
    )
    assert result["status"] == "PASS"
    assert all(item["status"] == "PASS" for item in result["checks"])
