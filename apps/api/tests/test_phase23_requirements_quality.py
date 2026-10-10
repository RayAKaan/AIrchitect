"""Accuracy and quality regression tests for Phase 23."""
from __future__ import annotations
import json
from pathlib import Path
from app.domains.requirements.extractor import DeterministicRequirementExtractor
from app.domains.requirements.quality import blocking_parameters,validate_requirement_candidates,validation_status
FIXTURES=Path(__file__).resolve().parents[1]/"tests"/"fixtures"/"requirements_accuracy_cases.json"
def cases(): return json.loads(FIXTURES.read_text(encoding="utf-8"))
def normalized(rows):
    return {(c.parameter,float(c.normalized_value) if isinstance(c.normalized_value,(int,float)) and not isinstance(c.normalized_value,bool) else c.normalized_value) for c in rows}
def test_accuracy_fixture_cases_match_exactly():
    extractor=DeterministicRequirementExtractor()
    for case in cases():
        expected={(p,float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) else v) for p,v in case["expected"]}
        assert normalized(extractor.extract(case["brief"]))==expected,case["id"]
def test_extraction_is_deterministic_and_method_versioned():
    brief="Six-floor retail building in Riyadh with 18,000 m² GFA on a 3,000 m² site."
    extractor=DeterministicRequirementExtractor()
    assert extractor.extract(brief)==extractor.extract(brief)
    assert all(c.extraction_method=="deterministic_pattern_v3" for c in extractor.extract(brief))
def test_invalid_nonpositive_values_are_blocking():
    brief="A commercial building with 0 floors and 0 m² GFA."
    issues=validate_requirement_candidates(DeterministicRequirementExtractor().extract(brief),brief)
    assert validation_status(issues)=="BLOCKED"
    assert blocking_parameters(issues)>={"floor_count","target_gfa"}
def test_comparative_constraints_are_not_exact_values():
    brief="A retail building with no more than 6 floors and up to SAR 5,000,000 budget."
    candidates=DeterministicRequirementExtractor().extract(brief)
    assert not any(c.parameter in {"floor_count","budget"} for c in candidates)
    issues=validate_requirement_candidates(candidates,brief)
    assert any(i["code"]=="UNSUPPORTED_CONSTRAINT_QUALIFIER" for i in issues)
    assert validation_status(issues)=="REVIEW_REQUIRED"
def test_conflicting_values_are_hard_errors():
    brief="The building has 3 floors, but later the brief says 5 floors."
    issues=validate_requirement_candidates(DeterministicRequirementExtractor().extract(brief),brief)
    assert any(i["code"]=="CONFLICTING_VALUES" for i in issues)
    assert "floor_count" in blocking_parameters(issues)
def test_unqualified_area_inference_requires_review():
    brief="A commercial building with 2,400 sqm."
    issues=validate_requirement_candidates(DeterministicRequirementExtractor().extract(brief),brief)
    assert any(i["code"]=="AMBIGUOUS_AREA_INFERENCE" for i in issues)
    assert validation_status(issues)=="REVIEW_REQUIRED"
def test_height_conflict_is_visible_but_nonblocking():
    brief="Commercial retail building with 6 floors, floor-to-floor height 4.2 m, building height 28 m."
    issues=validate_requirement_candidates(DeterministicRequirementExtractor().extract(brief),brief)
    assert any(i["code"]=="HEIGHT_FLOOR_INCONSISTENCY" for i in issues)
    assert validation_status(issues)=="REVIEW_REQUIRED"
    assert "floor_count" not in blocking_parameters(issues)
