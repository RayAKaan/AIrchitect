import pytest

from app.domains.design.s2_inputs import (
    S2DesignInputError,
    apply_s2_design_inputs,
    resolve_s2_design_inputs,
)
from app.domains.design.strategies import DesignCandidate, STRATEGIES


def test_s2_has_three_materially_distinct_strategy_families():
    ids = [strategy.id for strategy in STRATEGIES]
    assert ids == ["balanced", "compact", "low_rise"]
    assert len({strategy.name for strategy in STRATEGIES}) == 3


def sample_program(target_gfa=1000.0):
    return {
        "schema_version": "s2-program-v1",
        "use": "office",
        "target_gfa_m2": target_gfa,
        "floor_count": 2,
        "spaces": [
            {"id": "space-1", "space_type": "open_work", "quantity": 1,
             "target_area_m2": target_gfa * .6, "min_area_m2": target_gfa * .5,
             "max_area_m2": target_gfa * .7, "category": "primary"},
            {"id": "space-2", "space_type": "meeting", "quantity": 1,
             "target_area_m2": target_gfa * .4, "min_area_m2": target_gfa * .3,
             "max_area_m2": target_gfa * .5, "category": "primary"},
        ],
        "adjacencies": [
            {"from": "space-1", "to": "space-2", "relationship": "direct", "required": True},
        ],
        "assumptions": [{"parameter": "floor_height", "value": 3.6}],
        "unknowns": ["site_access_frontage"],
    }


def sample_envelope(max_gfa=1200.0, buildable_area=700.0, max_height=20.0):
    return {
        "schema_version": "s2-envelope-v1",
        "buildable_area_m2": buildable_area,
        "max_gfa_m2": max_gfa,
        "max_footprint_m2": 600.0,
        "max_height_m": max_height,
        "setback_m": 5.0,
        "site_orientation": {"long_axis_degrees_from_north": 30.0},
        "environmental_context": {"unknowns": ["solar_exposure", "prevailing_wind"]},
    }


def sample_candidate(*, gfa=1000.0, footprint=500.0, height=12.0):
    return DesignCandidate(
        candidate_key="balanced-1",
        strategy_id="balanced",
        strategy_version="1.0",
        parameters={"floor_count": 2, "footprint_width_m": 25.0, "footprint_depth_m": 20.0},
        metrics={
            "gross_floor_area_m2": gfa,
            "building_footprint_m2": footprint,
            "building_height_m": height,
        },
        constraint_results=[],
        tradeoffs=[],
        reasoning={},
        assumptions=[],
        unknowns=[],
        valid=True,
        invalid_reasons=[],
        score=0.1,
    )


def test_concept_candidate_consumes_programme_and_envelope_content():
    inputs = resolve_s2_design_inputs(sample_program(), sample_envelope())
    candidate = apply_s2_design_inputs(sample_candidate(), inputs)

    assert candidate.valid is True
    assert candidate.parameters["program_use"] == "office"
    assert len(candidate.parameters["program_space_schedule"]) == 2
    assert len(candidate.parameters["program_adjacencies"]) == 1
    assert candidate.parameters["setback_m"] == 5.0
    assert candidate.metrics["program_target_gfa_m2"] == 1000.0
    assert candidate.metrics["envelope_max_footprint_m2"] == 600.0
    assert candidate.reasoning["program_space_count"] == 2
    assert "solar_exposure" in candidate.unknowns
    assert "exact_buildable_polygon_placement" in candidate.unknowns


def test_program_target_cannot_exceed_the_current_envelope():
    with pytest.raises(S2DesignInputError) as exc_info:
        resolve_s2_design_inputs(sample_program(1500.0), sample_envelope(max_gfa=1200.0))
    assert exc_info.value.code == "PROGRAM_EXCEEDS_ENVELOPE"


def test_program_adjacencies_must_reference_real_spaces():
    program = sample_program()
    program["adjacencies"][0]["to"] = "missing-space"
    with pytest.raises(S2DesignInputError) as exc_info:
        resolve_s2_design_inputs(program, sample_envelope())
    assert exc_info.value.code == "S2_PROGRAM_INVALID"


def test_candidate_is_invalid_when_envelope_area_or_height_is_exceeded():
    inputs = resolve_s2_design_inputs(
        sample_program(),
        sample_envelope(buildable_area=400.0, max_height=10.0),
    )
    candidate = apply_s2_design_inputs(sample_candidate(footprint=500.0, height=12.0), inputs)
    assert candidate.valid is False
    assert "BUILDABLE_AREA_EXCEEDED" in candidate.invalid_reasons
    assert "MAX_HEIGHT_EXCEEDED" in candidate.invalid_reasons



def test_candidate_is_invalid_when_coverage_footprint_limit_is_exceeded():
    envelope = sample_envelope()
    envelope["max_footprint_m2"] = 450.0
    inputs = resolve_s2_design_inputs(sample_program(), envelope)
    candidate = apply_s2_design_inputs(sample_candidate(footprint=500.0), inputs)
    assert candidate.valid is False
    assert "MAX_FOOTPRINT_EXCEEDED" in candidate.invalid_reasons
