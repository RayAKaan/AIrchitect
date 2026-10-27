from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .rulepacks import RulePack, RuleDefinition


class FactValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: Any
    unit: str | None = None
    source_ref: str | None = None


class RegulatoryFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    title: str
    status: str
    severity: str
    subject: str
    observed: Any = None
    expected: Any = None
    unit: str | None = None
    source_refs: tuple[str, ...]
    message: str


class RegulatoryCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    pack_id: str
    pack_version: str
    pack_hash: str
    finding_count: int
    findings: tuple[RegulatoryFinding, ...]
    evaluation_hash: str


def _fact(facts: dict[str, FactValue | Any], subject: str) -> FactValue | None:
    value = facts.get(subject)
    if value is None:
        return None
    return value if isinstance(value, FactValue) else FactValue(value=value)


def _evaluate_rule(rule: RuleDefinition, facts: dict[str, FactValue | Any], context: dict[str, Any]) -> RegulatoryFinding:
    if not rule.applicability.matches(context):
        return RegulatoryFinding(
            rule_id=rule.rule_id, title=rule.title, status="not_applicable", severity=rule.severity,
            subject=rule.subject, expected=rule.expected, unit=rule.unit, source_refs=rule.source_refs,
            message="Rule is not applicable to the supplied project context.",
        )

    fact = _fact(facts, rule.subject)
    if fact is None:
        return RegulatoryFinding(
            rule_id=rule.rule_id, title=rule.title, status="missing_input", severity=rule.severity,
            subject=rule.subject, expected=rule.expected, unit=rule.unit, source_refs=rule.source_refs,
            message="Required fact is missing from the evaluation input.",
        )
    if rule.unit and fact.unit and rule.unit != fact.unit:
        return RegulatoryFinding(
            rule_id=rule.rule_id, title=rule.title, status="invalid_input", severity=rule.severity,
            subject=rule.subject, observed=fact.value, expected=rule.expected, unit=rule.unit,
            source_refs=rule.source_refs, message=f"Unit mismatch: expected {rule.unit}, received {fact.unit}.",
        )

    observed = fact.value
    try:
        if rule.check_type == "required":
            passed = observed is not None and observed != ""
        elif rule.check_type == "boolean":
            passed = observed is rule.expected
        elif rule.check_type == "numeric_min":
            passed = float(observed) >= float(rule.expected)
        elif rule.check_type == "numeric_max":
            passed = float(observed) <= float(rule.expected)
        elif rule.check_type == "enum":
            expected_values = rule.expected if isinstance(rule.expected, (list, tuple, set)) else [rule.expected]
            passed = observed in expected_values
        else:
            passed = False
    except (TypeError, ValueError):
        return RegulatoryFinding(
            rule_id=rule.rule_id, title=rule.title, status="invalid_input", severity=rule.severity,
            subject=rule.subject, observed=observed, expected=rule.expected, unit=rule.unit,
            source_refs=rule.source_refs, message="Fact could not be evaluated against the rule type.",
        )

    return RegulatoryFinding(
        rule_id=rule.rule_id, title=rule.title, status="pass" if passed else "fail", severity=rule.severity,
        subject=rule.subject, observed=observed, expected=rule.expected, unit=rule.unit,
        source_refs=rule.source_refs,
        message="Requirement satisfied." if passed else "Requirement not satisfied.",
    )


def evaluate_rule_pack(pack: RulePack, facts: dict[str, FactValue | Any], context: dict[str, Any] | None = None) -> RegulatoryCheckResult:
    if pack.status != "executable":
        raise ValueError("Catalog-only rule packs cannot be executed")
    project_context = context or {}
    findings = tuple(_evaluate_rule(rule, facts, project_context) for rule in pack.rules)
    payload = [finding.model_dump(mode="json") for finding in findings]
    evaluation_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return RegulatoryCheckResult(
        pack_id=pack.pack_id, pack_version=pack.version, pack_hash=pack.pack_hash,
        finding_count=len(findings), findings=findings, evaluation_hash=evaluation_hash,
    )
