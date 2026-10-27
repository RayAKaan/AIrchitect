from app.domains.regulatory.checks import evaluate_rule_pack
from app.domains.regulatory.evidence import EvidenceRecord, bind_evidence
from app.domains.regulatory.rulepacks import RuleDefinition, RulePack


def _result():
    pack = RulePack(
        pack_id="evidence-pack",
        profile_id="jurisdiction-neutral",
        version="1.0.0",
        source_refs=("source:pack",),
        rules=(RuleDefinition(
            rule_id="height-max",
            title="Maximum height",
            subject="height",
            check_type="numeric_max",
            expected=20,
            unit="m",
            source_refs=("source:height",),
        ),),
    )
    return evaluate_rule_pack(pack, {"height": 18})


def test_evidence_binding_distinguishes_missing_declared_and_verified():
    result = _result()
    missing = bind_evidence(result, ())
    assert missing.coverage_ratio == 0
    assert missing.findings[0].evidence_status == "missing"

    declared = bind_evidence(result, (EvidenceRecord(evidence_id="e1", source_ref="source:height", title="Reviewed source"),))
    assert declared.coverage_ratio == 1
    assert declared.verified_count == 0
    assert declared.findings[0].evidence_status == "declared"

    verified = bind_evidence(result, (EvidenceRecord(
        evidence_id="e1", source_ref="source:height", title="Reviewed source", verification_status="verified", reviewer_ref="review-1"
    ),))
    assert verified.verified_count == 1
    assert verified.findings[0].evidence_status == "verified"
    assert verified.binding_hash == bind_evidence(result, (EvidenceRecord(
        evidence_id="e1", source_ref="source:height", title="Reviewed source", verification_status="verified", reviewer_ref="review-1"
    ),)).binding_hash
