from uuid import uuid4
from .schemas import RegulatoryEvaluationRequest, RegulatoryEvaluationResponse, RegulatoryRuleResult


def _evaluate(rule, facts):
    if rule.field not in facts or facts[rule.field] is None:
        return 'unknown', None, 'Required project fact is missing.'
    value = facts[rule.field]
    try:
        op = rule.operator
        if op == 'exists': passed = value is not None
        elif op == 'eq': passed = value == rule.threshold
        elif op == 'in': passed = value in rule.threshold
        else:
            if isinstance(value, bool) or isinstance(rule.threshold, bool):
                raise TypeError
            a, b = float(value), float(rule.threshold)
            passed = {'lte': a <= b, 'lt': a < b, 'gte': a >= b, 'gt': a > b}[op]
    except (TypeError, ValueError, KeyError):
        return 'unknown', value, 'Fact and threshold are incompatible with the configured operator.'
    return ('pass' if passed else 'fail'), value, 'Configured rule condition evaluated true.' if passed else 'Configured rule condition evaluated false.'


def evaluate(request: RegulatoryEvaluationRequest) -> RegulatoryEvaluationResponse:
    results = []
    for rule in request.rules:
        status, observed, reason = _evaluate(rule, request.facts)
        results.append(RegulatoryRuleResult(rule_id=rule.rule_id, title=rule.title, status=status,
            observed_value=observed, threshold=rule.threshold, unit=rule.unit,
            source_name=rule.source_name, source_reference=rule.source_reference,
            source_version=rule.source_version, reason=reason))
    counts = {s: sum(r.status == s for r in results) for s in ('pass', 'fail', 'unknown')}
    return RegulatoryEvaluationResponse(evaluation_id=str(uuid4()), project_id=request.project_id,
        source_revision=request.source_revision, jurisdiction=request.jurisdiction,
        ruleset_id=request.ruleset_id, ruleset_version=request.ruleset_version,
        results=results, summary=counts)
