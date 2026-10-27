from app.domains.design.compiler import compile_design_intent
from app.domains.design.intent import AdjacencyRequirement, DesignIntent, RoomRequirement


def test_compiler_builds_canonical_spaces_with_target_areas() -> None:
    intent = DesignIntent(
        project_id="project",
        site_id="site",
        site_width_m=20,
        site_depth_m=20,
        rooms=(
            RoomRequirement(room_id="living", name="Living", target_area_m2=20),
            RoomRequirement(room_id="kitchen", name="Kitchen", target_area_m2=12),
        ),
        adjacencies=(AdjacencyRequirement(first_room_id="living", second_room_id="kitchen", relationship="near"),),
    )
    result = compile_design_intent(intent)
    assert result.model.revision == 1
    assert len(result.model.spaces) == 2
    assert all(space.level_id == "level-0" for space in result.model.spaces)


def test_compilation_is_deterministic() -> None:
    intent = DesignIntent(
        project_id="project",
        site_id="site",
        site_width_m=20,
        site_depth_m=20,
        rooms=(RoomRequirement(room_id="a", name="A", target_area_m2=16), RoomRequirement(room_id="b", name="B", target_area_m2=9)),
    )
    first = compile_design_intent(intent)
    second = compile_design_intent(intent)
    assert first.model == second.model
    assert first.warnings == second.warnings
