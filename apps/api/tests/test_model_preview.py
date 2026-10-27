from app.domains.design.intent import DesignIntent, RoomRequirement
from app.domains.design.preview import build_model_preview


def test_preview_contains_model_and_geometry_with_shared_identity() -> None:
    intent = DesignIntent(
        project_id="project",
        site_id="site",
        site_width_m=20,
        site_depth_m=20,
        rooms=(
            RoomRequirement(room_id="living", name="Living", target_area_m2=20),
            RoomRequirement(room_id="bedroom", name="Bedroom", target_area_m2=12),
        ),
    )
    preview = build_model_preview(intent)
    assert len(preview.model.spaces) == 2
    assert preview.model.walls
    assert preview.geometry
    assert {mesh.source_model_hash for mesh in preview.geometry}
    assert len({mesh.source_model_hash for mesh in preview.geometry}) == 1
