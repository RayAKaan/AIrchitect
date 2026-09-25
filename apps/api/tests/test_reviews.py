import pytest
from pydantic import ValidationError
from app.domains.reviews.schemas import ReviewCreate, DeliverableCreate

def test_review_requires_substantive_rationale():
    with pytest.raises(ValidationError):
        ReviewCreate(project_id='p',artifact_id='a',artifact_version='v1',source_hash='h',decision='rejected',rationale='no')

def test_review_decision_is_allowlisted():
    with pytest.raises(ValidationError):
        ReviewCreate(project_id='p',artifact_id='a',artifact_version='v1',source_hash='h',decision='approved',rationale='Detailed rationale')

def test_deliverable_requires_explicit_currentness_and_validation():
    with pytest.raises(ValidationError):
        DeliverableCreate(project_id='p',artifact_id='a',artifact_version='v1',source_hash='h',title='Feasibility',summary='Summary',validation_status='approved',current=True)

def test_deliverable_accepts_incomplete_but_marks_currentness():
    d=DeliverableCreate(project_id='p',artifact_id='a',artifact_version='v1',source_hash='h',title='Feasibility',summary='Summary',validation_status='incomplete',current=False)
    assert d.validation_status=='incomplete' and not d.current
