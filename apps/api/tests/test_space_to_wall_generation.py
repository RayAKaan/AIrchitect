import pytest

from app.domains.design.compiler import compile_design_intent
from app.domains.design.intent import DesignIntent, RoomRequirement
from app.domains.design.walls import derive_walls_from_spaces, with_generated_walls


def make_model():
    intent = DesignIntent(
        project_id="project",
        site_id="site",
        site_width_m=20,
        site_depth_m=20,
        rooms=(
            RoomRequirement(room_id="a", name="A", target_area_m2=12),
            RoomRequirement(room_id="b", name="B", target_area_m2=12),
        ),
    )
    return compile_design_intent(intent).model


def test_space_boundaries_produce_deterministic_walls() -> None:
    model = make_model()
    first = derive_walls_from_spaces(model)
    second = derive_walls_from_spaces(model)
    assert first == second
    assert len(first) == 7
    assert sum(len(wall.space_ids) == 2 for wall in first) == 1
    assert all(wall.height_m == 3 for wall in first)


def test_generated_walls_are_attached_as_a_new_model_revision_state() -> None:
    model = make_model()
    result = with_generated_walls(model)
    assert result.revision == model.revision
    assert len(result.walls) == 7
    assert model.walls == ()


def test_existing_walls_fail_closed() -> None:
    model = with_generated_walls(make_model())
    with pytest.raises(ValueError, match="already contains walls"):
        derive_walls_from_spaces(model)
