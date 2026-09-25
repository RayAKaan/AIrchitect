import pytest
from pydantic import ValidationError
from app.domains.structure.schemas import StructuralConceptRequest
from app.domains.structure.engine import generate

HASH = 'a' * 64

def request(**overrides):
    data = dict(project_id='p1', geometry_artifact_id='geom-123', geometry_sha256=HASH,
        source_revision=3, footprint_width_m=24, footprint_depth_m=16, floors=4,
        floor_to_floor_m=3.6, preferred_max_bay_m=8)
    data.update(overrides)
    return StructuralConceptRequest(**data)

def test_grid_is_deterministic_and_bounded():
    a, b = generate(request()), generate(request())
    assert a.concept_id == b.concept_id
    assert a.grid == b.grid
    assert a.grid['nominal_max_bay_m'] <= 8.0001
    assert a.status == 'concept_only'

def test_provenance_is_carried_forward():
    result = generate(request(source_revision=9, geometry_sha256='b' * 64))
    assert result.source_revision == 9
    assert result.geometry_sha256 == 'b' * 64

def test_unknown_load_is_explicit_and_not_invented():
    result = generate(request())
    assert result.preliminary_quantities['load_basis'] == 'not_provided'
    assert result.input_completeness['imposed_load_provided'] is False

def test_user_load_is_labeled_as_user_supplied():
    result = generate(request(imposed_load_kpa=4.0))
    assert result.preliminary_quantities['load_basis'] == 'user_supplied:4.0 kPa'

def test_rejects_invalid_hash_and_dimensions():
    with pytest.raises(ValidationError):
        request(geometry_sha256='bad')
    with pytest.raises(ValidationError):
        request(footprint_width_m=0)

def test_never_claims_engineering_or_code_approval():
    result = generate(request())
    assert result.checks['structural_capacity_checked'] is False
    assert result.checks['code_compliance_checked'] is False
    assert 'not a structural design' in result.limitations[0]
