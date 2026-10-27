from app.domains.regulatory.checks import evaluate_rule_pack
from app.domains.regulatory.evidence import EvidenceRecord, bind_evidence
from app.domains.regulatory.impact import calculate_regulatory_impact
from app.domains.regulatory.regeneration import RegenerationResult
from app.domains.regulatory.rulepacks import RuleDefinition, RulePack
from app.domains.regulatory.verification import verify_regulatory_state


def _state():
    pack = RulePack(
        pack_id="verify",
        profile_id="jurisdiction-neutral",
        version="1.0.0",
        source_refs=("source:verify",),
        rules=(RuleDefinition(
            rule_id="height-max", title="Maximum height", subject="height", check_type="numeric_max",
            expected=20, unit="m", source_refs=("source:height",)
        ),),
    )
    result = evaluate_rule_pack(pack, {"height": 18})
    evidence = bind_evidence(result, (EvidenceRecord(
        evidence_id="e1", source_ref="source:height", title="Reviewed source", verification_status="verified", reviewer_ref="reviewer"
    ),))
    impact = calculate_regulatory_impact("rev-1", ())
    return result, evidence, impact


def test_clean_state_is_verified():
    result, evidence, impact = _state()
    verification = verify_regulatory_state("rev-1", result, evidence, impact)
    assert verification.status == "verified"
    assert verification.failed_finding_count == 0
    assert verification.missing_evidence_count == 0
    assert verification.unverified_evidence_count == 0
    assert verification.verification_hash


def test_unverified_evidence_blocks_verification():
    result, _, impact = _state()
    declared = bind_evidence(result, (EvidenceRecord(evidence_id="e1", source_ref="source:height", title="Source"),))
    verification = verify_regulatory_state("rev-1", result, declared, impact)
    assert verification.status == "blocked"
    assert verification.unverified_evidence_count == 1


def test_failed_requirement_is_verified_with_findings_not_compliance_approved():
    result, _, impact = _state()
    failed = evaluate_rule_pack(result.model_copy(update={}).model_copy(update={}), {"height": 30})
    evidence = bind_evidence(failed, (EvidenceRecord(
        evidence_id="e1", source_ref="source:height", title="Reviewed source", verification_status="verified", reviewer_ref="reviewer"
    ),))
    verification = verify_regulatory_state("rev-1", failed, evidence, impact)
    assert verification.status == "verified_with_findings"
    assert verification.failed_finding_count == 1
    assert any("does not constitute compliance approval" in message for message in verification.messages)
