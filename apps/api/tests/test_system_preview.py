from app.domains.design.intent import DesignIntent, RoomRequirement
from app.domains.design.system_preview import build_system_preview


def test_system_preview_connects_design_model_geometry_cad_and_analysis() -> None:
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
    result = build_system_preview(intent)
    assert result.preview.model.project_id == "project"
    assert result.scene.model_hash == result.cad_job.provenance.model_hash
    assert result.scene.nodes
    assert result.cad_job.request.elements
    assert result.loads.model_hash == result.cad_job.provenance.model_hash
    assert result.quantities.model_hash == result.cad_job.provenance.model_hash
    assert result.regulatory.model_hash == result.cad_job.provenance.model_hash
    assert result.regulatory.passed is True


def test_system_preview_rejects_invalid_room_level_index() -> None:
    try:
        DesignIntent(
            project_id="project",
            site_id="site",
            site_width_m=20,
            site_depth_m=20,
            floors=1,
            rooms=(RoomRequirement(room_id="room", name="Room", target_area_m2=10, level_index=1),),
        )
    except ValueError as exc:
        assert "level_index" in str(exc)
    else:
        raise AssertionError("invalid level index was accepted")
