from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .checks import RegulatoryCheckResult
from .evidence import EvidenceBindingResult
from .impact import RegulatoryImpactResult
from .regeneration import RegenerationResult


class RegulatoryVerification(BaseModel):
    model_config = ConfigDict(frozen=True)

    revision_id: str
    status: Literal["verified", "verified_with_findings", "blocked"]
    finding_count: int
    failed_finding_count: int
    missing_evidence_count: int
    unverified_evidence_count: int
    stale_target_count: int
    regenerated_target_count: int
    verification_hash: str
    messages: tuple[str, ...]


def verify_regulatory_state(
    revision_id: str,
    check_result: RegulatoryCheckResult,
    evidence: EvidenceBindingResult,
    impact: RegulatoryImpactResult,
    regeneration: RegenerationResult | None = None,
) -> RegulatoryVerification:
    messages: list[str] = []
    blocked = False

    if check_result.pack_hash == "" or check_result.evaluation_hash == "":
        blocked = True
        messages.append("Regulatory evaluation is missing its deterministic hashes.")
    if evidence.evaluation_hash != check_result.evaluation_hash:
        blocked = True
        messages.append("Evidence binding does not match the evaluated findings.")
    if evidence.finding_count != check_result.finding_count:
        blocked = True
        messages.append("Evidence binding finding count does not match evaluation.")
    if impact.revision_id != revision_id:
        blocked = True
        messages.append("Impact analysis revision does not match verification revision.")
    if impact.impacted_targets:
        if regeneration is None:
            blocked = True
            messages.append("Regulatory state remains stale and has not been regenerated.")
        elif not set(impact.impacted_targets).issubset(set(regeneration.executed_targets) | {"regulatory-verification"}):
            blocked = True
            messages.append("Not all stale regulatory targets were regenerated.")
    missing = sum(item.evidence_status == "missing" for item in evidence.findings)
    unverified = sum(item.evidence_status == "declared" for item in evidence.findings)
    if missing:
        blocked = True
        messages.append("One or more findings have no bound evidence.")
    if unverified:
        blocked = True
        messages.append("One or more findings have evidence that has not been reviewer-verified.")

    failed = sum(item.finding.status == "fail" for item in evidence.findings)
    if failed:
        messages.append("Regulatory findings contain unmet requirements; technical verification does not constitute compliance approval.")

    if not messages:
        messages.append("Regulatory state is internally consistent, evidenced, and current for the supplied revision.")
    status: Literal["verified", "verified_with_findings", "blocked"] = "blocked" if blocked else ("verified_with_findings" if failed else "verified")
    payload = {
        "revision_id": revision_id,
        "status": status,
        "finding_count": check_result.finding_count,
        "failed_finding_count": failed,
        "missing_evidence_count": missing,
        "unverified_evidence_count": unverified,
        "stale_target_count": len(impact.impacted_targets),
        "regenerated_target_count": len(regeneration.executed_targets) if regeneration else 0,
    }
    verification_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return RegulatoryVerification(
        **payload,
        verification_hash=verification_hash,
        messages=tuple(messages),
    )
