from app.domains.design.intent import DesignIntent, RoomRequirement
from app.domains.design.system_preview import build_system_preview
from app.domains.design.system_preview_routes import _serialize


def test_system_preview_serialization_contains_renderable_meshes_and_provenance() -> None:
    intent = DesignIntent(
        project_id="project",
        site_id="site",
        site_width_m=20,
        site_depth_m=20,
        rooms=(RoomRequirement(room_id="living", name="Living", target_area_m2=20),),
    )
    payload = _serialize(build_system_preview(intent))
    scene = payload["scene"]
    assert payload["read_only"] is True
    assert scene["model_hash"]
    assert scene["nodes"]
    assert scene["meshes"]
    assert scene["meshes"][0]["geometry_hash"]
    assert set(scene["bounds"]) == {"minimum", "maximum"}
    assert payload["cad"]["provenance"]["model_hash"] == scene["model_hash"]
