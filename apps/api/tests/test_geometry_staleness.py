import pytest

from app.domains.geometry.staleness import GeometryStaleness, require_current_geometry


def test_matching_dependencies_are_current() -> None:
    value = GeometryStaleness("g", "world", "world", "design", "design")
    assert not value.stale
    assert value.reasons == ()
    require_current_geometry(value)


@pytest.mark.parametrize(
    ("world_current", "design_current", "reasons"),
    [
        ("new-world", "design", ("WORLD_MODEL_CHANGED",)),
        ("world", "new-design", ("DESIGN_CHANGED",)),
        ("new-world", "new-design", ("WORLD_MODEL_CHANGED", "DESIGN_CHANGED")),
    ],
)
def test_changed_dependencies_mark_geometry_stale(world_current, design_current, reasons) -> None:
    value = GeometryStaleness("g", world_current, "world", design_current, "design")
    assert value.stale
    assert value.reasons == reasons
    with pytest.raises(ValueError, match="GEOMETRY_STALE"):
        require_current_geometry(value)
