import pytest

from app.domains.regulatory.regeneration import (
    SelectiveRegenerationRequest,
    build_regeneration_plan,
    execute_selective_regeneration,
)
from app.domains.regulatory.rulepacks import RuleDefinition, RulePack


def _pack() -> RulePack:
    return RulePack(
        pack_id="regen",
        profile_id="jurisdiction-neutral",
        version="1.0.0",
        source_refs=("source:regen",),
        rules=(RuleDefinition(
            rule_id="height-max", title="Maximum height", subject="height", check_type="numeric_max",
            expected=20, unit="m", source_refs=("source:height",)
        ),),
    )


def test_plan_is_ordered_and_hashed():
    plan = build_regeneration_plan("rev-1", ("regulatory-evidence", "regulatory-findings"))
    assert plan.tasks[0].target == "regulatory-evidence"
    assert plan.tasks[0].depends_on == ("regulatory-findings",)
    assert plan.plan_hash == build_regeneration_plan("rev-1", ("regulatory-evidence", "regulatory-findings")).plan_hash


def test_findings_only_regeneration_does_not_execute_evidence():
    result = execute_selective_regeneration(SelectiveRegenerationRequest(
        revision_id="rev-1", targets=("regulatory-findings",), pack=_pack(), facts={"height": 18}
    ))
    assert result.executed_targets == ("regulatory-findings",)
    assert result.evidence is None
    assert result.findings.findings[0].status == "pass"


def test_evidence_requires_findings_or_existing_result():
    with pytest.raises(ValueError, match="requires findings"):
        execute_selective_regeneration(SelectiveRegenerationRequest(
            revision_id="rev-1", targets=("regulatory-evidence",)
        ))
