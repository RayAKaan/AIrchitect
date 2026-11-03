from __future__ import annotations

from shapely.geometry import Polygon, mapping

from app.domains.spatial_layout.service import SpatialLayoutError, build_spatial_layout
from app.domains.semantic_model.service import canonical_hash
from app.domains.commands.regeneration_executor import RegenerationHandlerRegistry, RegenerationInput


def _inputs(*, relationship: str = "direct", footprint_width: float = 20.0, footprint_depth: float = 20.0):
    site = Polygon([
        (-0.005, -0.005),
        (0.005, -0.005),
        (0.005, 0.005),
        (-0.005, 0.005),
    ])
    program = {
        "schema_version": "s2-program-v2",
        "use": "office",
        "target_gfa_m2": 800.0,
        "floor_count": 2,
        "spaces": [
            {
                "id": "lobby",
                "name": "Reception",
                "space_type": "reception",
                "category": "public",
                "quantity": 1,
                "target_area_m2": 80.0,
                "min_area_m2": 70.0,
                "max_area_m2": 90.0,
            },
            {
                "id": "work",
                "name": "Open Work",
                "space_type": "open_work",
                "category": "primary",
                "quantity": 1,
                "target_area_m2": 720.0,
                "min_area_m2": 680.0,
                "max_area_m2": 760.0,
            },
        ],
        "adjacencies": [
            {"from": "lobby", "to": "work", "relationship": relationship, "required": True},
        ],
    }
    envelope = {
        "buildable_area_m2": 1_000_000.0,
        "buildable_polygon": mapping(site),
        "max_footprint_m2": 500.0,
        "max_gfa_m2": 1_000.0,
        "max_height_m": 10.0,
    }
    parameters = {
        "floor_count": 2,
        "floor_to_floor_height_m": 3.2,
        "footprint_width_m": footprint_width,
        "footprint_depth_m": footprint_depth,
        "orientation_degrees": 0.0,
        "translation_m": {"x": 0.0, "y": 0.0, "z": 0.0},
    }
    metrics = {"gross_floor_area_m2": 800.0, "building_height_m": 6.4}
    return program, envelope, parameters, metrics


def _build(*, relationship: str = "direct", footprint_width: float = 20.0, footprint_depth: float = 20.0):
    program, envelope, parameters, metrics = _inputs(
        relationship=relationship,
        footprint_width=footprint_width,
        footprint_depth=footprint_depth,
    )
    return build_spatial_layout(
        project_id="project-1",
        project_version_id="version-1",
        world_model_hash="a" * 64,
        program=program,
        envelope=envelope,
        alternative_id="alternative-1",
        design_parameters=parameters,
        design_metrics=metrics,
    )


def test_layout_is_deterministic_and_reconciles_each_floor_and_total_gfa():
    first = _build()
    second = _build()

    assert first["layout_hash"] == second["layout_hash"]
    assert len(first["floor_plates"]) == 2
    assert len(first["spaces"]) == 4
    assert first["area_reconciliation"]["reconciled"] is True
    assert first["area_reconciliation"]["allocated_space_area_m2"] == 800.0
    assert first["status"] == "REVIEW_REQUIRED"
    assert all(item["status"] == "SATISFIED" for item in first["adjacencies"])
    assert all(item["geometry_status"] == "DERIVED_PRELIMINARY" for item in first["spaces"])
    assert "egress_routes" in first["unknowns"]


def test_required_relationships_outside_supported_topology_are_explicitly_deferred():
    layout = _build(relationship="service")

    assert layout["status"] == "REVIEW_REQUIRED"
    assert all(item["status"] == "DEFERRED_TO_TOPOLOGY" for item in layout["adjacencies"])
    assert "required_program_adjacencies" in layout["unknowns"]


def test_footprint_must_fit_inside_the_buildable_envelope():
    try:
        _build(footprint_width=2_000.0, footprint_depth=2_000.0)
    except SpatialLayoutError as exc:
        assert exc.code in {
            "LAYOUT_FOOTPRINT_EXCEEDS_ENVELOPE",
            "LAYOUT_MAX_FOOTPRINT_EXCEEDED",
            "LAYOUT_FOOTPRINT_NOT_CONTAINED",
        }
    else:
        raise AssertionError("An oversized footprint must not be placed")


def test_programme_area_must_reconcile_to_target_gfa():
    program, envelope, parameters, metrics = _inputs()
    program["spaces"][0]["target_area_m2"] = 100.0
    program["spaces"][0]["min_area_m2"] = 90.0
    program["spaces"][0]["max_area_m2"] = 110.0
    try:
        build_spatial_layout(
            project_id="project-1",
            project_version_id="version-1",
            world_model_hash="a" * 64,
            program=program,
            envelope=envelope,
            alternative_id="alternative-1",
            design_parameters=parameters,
            design_metrics=metrics,
        )
    except SpatialLayoutError as exc:
        assert exc.code == "LAYOUT_PROGRAM_GFA_MISMATCH"
    else:
        raise AssertionError("A non-reconciled programme must fail closed")


def test_concept_and_program_floor_counts_must_match():
    program, envelope, parameters, metrics = _inputs()
    parameters["floor_count"] = 3
    try:
        build_spatial_layout(
            project_id="project-1",
            project_version_id="version-1",
            world_model_hash="a" * 64,
            program=program,
            envelope=envelope,
            alternative_id="alternative-1",
            design_parameters=parameters,
            design_metrics=metrics,
        )
    except SpatialLayoutError as exc:
        assert exc.code == "LAYOUT_FLOOR_COUNT_MISMATCH"
    else:
        raise AssertionError("A floor-count mismatch must fail closed")


def test_programme_and_spatial_layout_routes_are_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/program/generate" in paths
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/envelope/generate" in paths
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/concepts/generate" in paths
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/spatial-layout/generate" in paths
    assert "/api/v1/projects/{project_id}/versions/{version_ref}/spatial-layout" in paths


def test_canonical_building_translation_is_not_silently_relocated():
    program, envelope, parameters, metrics = _inputs()
    parameters["translation_m"] = {"x": 2_000.0, "y": 0.0, "z": 0.0}
    try:
        build_spatial_layout(
            project_id="project-1",
            project_version_id="version-1",
            world_model_hash="a" * 64,
            program=program,
            envelope=envelope,
            alternative_id="alternative-1",
            design_parameters=parameters,
            design_metrics=metrics,
        )
    except SpatialLayoutError as exc:
        assert exc.code == "LAYOUT_FOOTPRINT_NOT_CONTAINED"
    else:
        raise AssertionError("An out-of-envelope canonical translation must not be relocated")


def test_spatial_layout_regeneration_uses_current_program_envelope_and_selected_alternative():
    program, envelope, parameters, metrics = _inputs()
    request = RegenerationInput(
        artifact_type="spatial_layout",
        source_revision_hash="a" * 64,
        payload={
            "regeneration_request": {
                "project_id": "project-1",
                "project_version_id": "version-1",
            },
        },
        dependencies={
            "architectural_program": {"payload": program},
            "planning_envelope": {"payload": envelope},
            "design_alternative": {
                "payload": {
                    "parameters": parameters,
                    "metrics": {**metrics, "design_hash": "d" * 64},
                    "design_hash": "d" * 64,
                },
                "selected_alternative_id": "alternative-1",
            },
        },
    )
    result = RegenerationHandlerRegistry().execute(request)
    expected = build_spatial_layout(
        project_id="project-1",
        project_version_id="version-1",
        world_model_hash="a" * 64,
        program=program,
        envelope=envelope,
        alternative_id="alternative-1",
        design_parameters=parameters,
        design_metrics={**metrics, "design_hash": "d" * 64},
    )
    expected["regeneration_request"] = {
        "project_id": "project-1",
        "project_version_id": "version-1",
    }
    expected_hash_input = dict(expected)
    expected_hash_input.pop("layout_hash", None)
    expected["layout_hash"] = canonical_hash(expected_hash_input)
    assert result.payload["layout_hash"] == expected["layout_hash"]
    assert result.output_hash
