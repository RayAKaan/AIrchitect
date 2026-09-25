import pytest
from pydantic import ValidationError
from app.domains.regulatory.schemas import RegulatoryEvaluationRequest
from app.domains.regulatory.engine import evaluate


def rule(rule_id='setback', operator='gte', threshold=5):
    return {'rule_id': rule_id, 'title': 'Minimum setback', 'field': 'setback_m',
        'operator': operator, 'threshold': threshold, 'unit': 'm',
        'source_name': 'User-configured source', 'source_reference': 'REF-001', 'source_version': '2026.1'}

def request(rules=None, facts=None):
    return RegulatoryEvaluationRequest(project_id='p1', source_revision=2,
        jurisdiction='user-specified jurisdiction', ruleset_id='custom', ruleset_version='1',
        rules=rules if rules is not None else [rule()], facts=facts if facts is not None else {'setback_m': 6})

def test_configured_rule_passes_with_provenance():
    out = evaluate(request())
    assert out.results[0].status == 'pass'
    assert out.results[0].source_reference == 'REF-001'
    assert out.status == 'preliminary_only'

def test_rule_fails_when_condition_false():
    assert evaluate(request(facts={'setback_m': 3})).results[0].status == 'fail'

def test_missing_fact_is_unknown_not_pass():
    out = evaluate(request(facts={}))
    assert out.results[0].status == 'unknown'
    assert out.summary == {'pass': 0, 'fail': 0, 'unknown': 1}

def test_incompatible_numeric_fact_is_unknown():
    assert evaluate(request(facts={'setback_m': 'not-a-number'})).results[0].status == 'unknown'

def test_duplicate_rule_ids_rejected():
    with pytest.raises(ValidationError):
        request(rules=[rule(), rule()])

def test_missing_threshold_rejected():
    with pytest.raises(ValidationError):
        request(rules=[{k:v for k,v in rule().items() if k != 'threshold'}])

def test_exists_operator():
    r = rule(operator='exists', threshold=None)
    assert evaluate(request(rules=[r])).results[0].status == 'pass'
