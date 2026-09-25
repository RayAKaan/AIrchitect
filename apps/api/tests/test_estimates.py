import pytest
from pydantic import ValidationError
from app.domains.estimates.schemas import EstimateRequest
from app.domains.estimates.engine import calculate

GEO = 'a' * 64

def req():
    return EstimateRequest(project_id='p1', source_revision=3, geometry_artifact_id='geom-abc', geometry_sha256=GEO,
        quantities=[{'code':'gfa','description':'Gross floor area','quantity':1000,'unit':'m2','source':'Geometry artifact geom-abc'}],
        lines=[{'quantity_code':'gfa','category':'Shell','rate':{'low':1500,'base':1800,'high':2200,'source':'User estimate','rate_schedule_version':'ksa-retail-v1'}}],
        contingency_pct=10)

def test_cost_scenarios_and_contingency_are_deterministic():
    a, b = calculate(req()), calculate(req())
    assert a.model_dump() == b.model_dump()
    assert (a.subtotal_low_sar, a.subtotal_base_sar, a.subtotal_high_sar) == (1500000,1800000,2200000)
    assert (a.total_low_sar, a.total_base_sar, a.total_high_sar) == (1650000,1980000,2420000)
    assert a.estimate_id.startswith('est-') and a.status == 'preliminary'

def test_rate_band_order_is_enforced():
    with pytest.raises(ValidationError):
        EstimateRequest.model_validate({'project_id':'p','source_revision':1,'geometry_artifact_id':'g','geometry_sha256':GEO,'quantities':[{'code':'gfa','description':'GFA','quantity':1,'unit':'m2','source':'input'}],'lines':[{'quantity_code':'gfa','category':'x','rate':{'low':200,'base':100,'high':300,'source':'x','rate_schedule_version':'v1'}}]})

def test_unknown_quantity_reference_rejected():
    with pytest.raises(ValidationError):
        EstimateRequest(project_id='p',source_revision=1,geometry_artifact_id='g',geometry_sha256=GEO,
          quantities=[{'code':'a','description':'A','quantity':1,'unit':'m2','source':'input'}],
          lines=[{'quantity_code':'missing','category':'x','rate':{'low':1,'base':2,'high':3,'source':'input','rate_schedule_version':'v1'}}])

def test_source_geometry_hash_is_bound_into_estimate_identity():
    first = calculate(req())
    changed = req().model_copy(update={'geometry_sha256':'b'*64})
    assert calculate(changed).estimate_id != first.estimate_id
