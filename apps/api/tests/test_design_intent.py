import pytest
from pydantic import ValidationError

from app.domains.design.intent import AdjacencyRequirement, DesignIntent, RoomRequirement


def room(room_id: str, area: float) -> RoomRequirement:
    return RoomRequirement(room_id=room_id, name=room_id.title(), target_area_m2=area)


def test_design_intent_accepts_valid_program() -> None:
    intent = DesignIntent(
        project_id="project",
        site_id="site",
        site_width_m=20,
        site_depth_m=30,
        rooms=(room("living", 24), room("kitchen", 12)),
        adjacencies=(AdjacencyRequirement(first_room_id="living", second_room_id="kitchen", relationship="adjacent"),),
    )
    assert len(intent.rooms) == 2


def test_duplicate_rooms_are_rejected() -> None:
    with pytest.raises(ValidationError, match="room_id values must be unique"):
        DesignIntent(
            project_id="project",
            site_id="site",
            site_width_m=20,
            site_depth_m=30,
            rooms=(room("living", 24), room("living", 20)),
        )


def test_unknown_adjacency_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown room"):
        DesignIntent(
            project_id="project",
            site_id="site",
            site_width_m=20,
            site_depth_m=30,
            rooms=(room("living", 24),),
            adjacencies=(AdjacencyRequirement(first_room_id="living", second_room_id="kitchen", relationship="near"),),
        )
