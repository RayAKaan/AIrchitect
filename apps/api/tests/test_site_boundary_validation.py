import pytest

from app.domains.site.validation import validate_boundary


def polygon(size: float = 0.001) -> dict:
    return {"type": "Polygon", "coordinates": [[[77.59, 12.97], [77.59 + size, 12.97], [77.59 + size, 12.97 + size], [77.59, 12.97 + size], [77.59, 12.97]]]}


def test_valid_boundary_projects_to_local_metric_crs() -> None:
    result = validate_boundary(polygon())
    assert result.area_m2 > 0
    assert result.perimeter_m > 0
    assert result.geojson["type"] == "Polygon"
    assert result.calculation_crs.startswith("+proj=aeqd")


def test_boundary_must_be_closed() -> None:
    value = polygon()
    value["coordinates"][0].pop()
    with pytest.raises(ValueError, match="SITE_BOUNDARY_RING_MUST_BE_CLOSED"):
        validate_boundary(value)


def test_self_intersection_is_rejected() -> None:
    value = {"type": "Polygon", "coordinates": [[[77.59, 12.97], [77.60, 12.98], [77.60, 12.97], [77.59, 12.98], [77.59, 12.97]]]}
    with pytest.raises(ValueError, match="SITE_BOUNDARY_INVALID_GEOMETRY"):
        validate_boundary(value)
