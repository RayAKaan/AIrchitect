from __future__ import annotations

import pytest

from app.cad_worker.ifc_io import IfcError, validate_round_trip


def _inspection():
    return {
        "schema": "IFC4",
        "elements": [
            {
                "canonical_element_id": "wall-1",
                "source_world_model_hash": "a" * 64,
                "has_representation": True,
                "predefined_type": "STANDARD",
            },
            {
                "canonical_element_id": "slab-1",
                "source_world_model_hash": "a" * 64,
                "has_representation": True,
                "predefined_type": "FLOOR",
            },
        ],
    }


def test_ifc4_round_trip_preserves_canonical_ids_geometry_and_source_lineage():
    result = validate_round_trip(
        _inspection(),
        expected_element_ids=("wall-1", "slab-1"),
        source_world_model_hash="a" * 64,
    )
    assert result == {
        "status": "PASS",
        "schema": "IFC4",
        "element_count": 2,
        "canonical_element_ids": ["slab-1", "wall-1"],
        "source_world_model_hash": "a" * 64,
    }


def test_ifc_round_trip_rejects_dropped_or_duplicate_canonical_ids():
    inspection = _inspection()
    inspection["elements"][1]["canonical_element_id"] = "wall-1"
    with pytest.raises(IfcError, match="duplicate canonical element IDs"):
        validate_round_trip(inspection, expected_element_ids=("wall-1", "slab-1"))


def test_ifc_round_trip_rejects_schema_and_geometry_loss():
    inspection = _inspection()
    inspection["schema"] = "IFC2X3"
    with pytest.raises(IfcError, match="schema mismatch"):
        validate_round_trip(inspection, expected_element_ids=("wall-1", "slab-1"))

    inspection = _inspection()
    inspection["elements"][0]["has_representation"] = False
    with pytest.raises(IfcError, match="without a geometric representation"):
        validate_round_trip(inspection, expected_element_ids=("wall-1", "slab-1"))


def test_ifc_round_trip_rejects_source_model_lineage_mismatch():
    inspection = _inspection()
    with pytest.raises(IfcError, match="lineage does not match"):
        validate_round_trip(
            inspection,
            expected_element_ids=("wall-1", "slab-1"),
            source_world_model_hash="b" * 64,
        )
