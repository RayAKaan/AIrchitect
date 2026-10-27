from app.domains.cad.canonical_export import (
    CanonicalCadRequestRejected,
    build_canonical_request,
)
from app.domains.cad.config import CadConfig
from app.domains.model.schemas import (
    ArchitecturalModel,
    Building,
    Level,
    Point3D,
    Site,
    Space,
)


def canonical_model() -> ArchitecturalModel:
    return ArchitecturalModel(
        project_id="project-1",
        revision=7,
        site=Site(id="site-1", width_m=50, depth_m=40),
        buildings=(Building(id="building-1", name="Main", site_id="site-1"),),
        levels=(Level(id="level-1", building_id="building-1", name="Ground", elevation_m=0, height_m=3),),
        spaces=(
            Space(
                id="space-1",
                name="Lobby",
                level_id="level-1",
                boundary=(
                    Point3D(x=0, y=0, z=0),
                    Point3D(x=10, y=0, z=0),
                    Point3D(x=10, y=8, z=0),
                    Point3D(x=0, y=8, z=0),
                ),
            ),
        ),
    )


def config(**overrides: object) -> CadConfig:
    values = {
        "artifact_root": "/tmp/airchitect-test-artifacts",
        "write_fcstd": True,
        "write_step": True,
        "write_ifc": True,
        "write_glb": True,
    }
    values.update(overrides)
    return CadConfig(**values)


def test_build_canonical_request_projects_authoritative_model() -> None:
    request = build_canonical_request(
        canonical_model(), project_name="Demo", config=config()
    )

    assert request.alternative_ref == "canonical-model:7"
    assert request.project_name == "Demo"
    assert len(request.elements) == 1
    element = request.elements[0]
    assert element.id == "space-1"
    assert element.source_reference
    assert element.base_elevation_m == 0
    assert element.height_m == 3
    assert element.metadata == {"canonical_element_type": "space", "level_id": "level-1"}
    assert request.options.write_ifc is True
    assert request.options.write_step is True


def test_requested_outputs_only_narrow_enabled_formats() -> None:
    request = build_canonical_request(
        canonical_model(),
        project_name="Demo",
        config=config(),
        requested_outputs=["ifc"],
    )

    assert request.options.write_ifc is True
    assert request.options.write_step is False
    assert request.options.write_glb is False
    assert request.options.write_fcstd is False


def test_requested_disabled_output_is_rejected() -> None:
    try:
        build_canonical_request(
            canonical_model(),
            project_name="Demo",
            config=config(write_ifc=False),
            requested_outputs=["ifc"],
        )
    except CanonicalCadRequestRejected as exc:
        assert exc.code == "CAD_NO_OUTPUTS_ENABLED"
    else:
        raise AssertionError("disabled-only output selection must be rejected")


def test_unknown_output_is_rejected() -> None:
    try:
        build_canonical_request(
            canonical_model(),
            project_name="Demo",
            config=config(),
            requested_outputs=["dwg"],
        )
    except CanonicalCadRequestRejected as exc:
        assert exc.code == "CAD_UNKNOWN_OUTPUT"
    else:
        raise AssertionError("unknown output must be rejected")
