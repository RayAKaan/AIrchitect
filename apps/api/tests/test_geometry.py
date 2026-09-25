import pytest
from pydantic import ValidationError
from app.domains.geometry.schemas import GeometryGenerateRequest
from app.domains.geometry.engine import generate


def request():
    return GeometryGenerateRequest(project_id='p1', source_revision=2, footprint_width_m=30,
        footprint_depth_m=20, options=[{'option_id':'b','floors':3,'floor_to_floor_m':4},
                                       {'option_id':'a','floors':2,'setback_m':2}])


def test_geometry_is_deterministic_and_sorted():
    req = request()
    first, second = generate(req), generate(req)
    assert [a.option_id for a in first] == ['a', 'b']
    assert [a.geometry_sha256 for a in first] == [a.geometry_sha256 for a in second]
    assert len(first[0].vertices) == 8 and len(first[0].faces) == 6


def test_quantities_are_derived_from_dimensions():
    a = generate(request())[0]
    assert a.footprint_area_m2 == 416
    assert a.gross_floor_area_m2 == 832
    assert a.gross_volume_m3 == 2995.2


def test_setback_cannot_consume_footprint():
    with pytest.raises(ValidationError):
        GeometryGenerateRequest(project_id='p', source_revision=1, footprint_width_m=10,
            footprint_depth_m=8, options=[{'option_id':'x','floors':2,'setback_m':4}])


def test_artifact_hash_changes_with_geometry():
    a = generate(request())[0]
    req = request().model_copy(update={'footprint_width_m': 31})
    b = generate(req)[0]
    assert a.geometry_sha256 != b.geometry_sha256
