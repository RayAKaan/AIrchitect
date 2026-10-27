from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .checks import RegulatoryCheckResult, RegulatoryFinding


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str = Field(min_length=1, max_length=128)
    source_ref: str = Field(min_length=1)
    title: str = Field(min_length=1)
    edition: str | None = None
    locator: str | None = None
    verification_status: Literal["declared", "verified", "rejected"] = "declared"
    reviewer_ref: str | None = None
    content_digest: str | None = None


class EvidenceBackedFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    finding: RegulatoryFinding
    evidence_ids: tuple[str, ...]
    evidence_status: Literal["missing", "declared", "verified"]


class EvidenceBindingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    evaluation_hash: str
    finding_count: int
    evidenced_count: int
    verified_count: int
    coverage_ratio: float
    findings: tuple[EvidenceBackedFinding, ...]
    binding_hash: str


def bind_evidence(result: RegulatoryCheckResult, records: tuple[EvidenceRecord, ...]) -> EvidenceBindingResult:
    by_source = {record.source_ref: record for record in records}
    bound: list[EvidenceBackedFinding] = []
    verified_count = 0
    evidenced_count = 0

    for finding in result.findings:
        matched = tuple(by_source[source] for source in finding.source_refs if source in by_source)
        statuses = {record.verification_status for record in matched}
        if not matched:
            status: Literal["missing", "declared", "verified"] = "missing"
        elif statuses == {"verified"} and len(matched) == len(finding.source_refs):
            status = "verified"
        elif "rejected" not in statuses:
            status = "declared"
        else:
            status = "missing"
        if status != "missing":
            evidenced_count += 1
        if status == "verified":
            verified_count += 1
        bound.append(EvidenceBackedFinding(finding=finding, evidence_ids=tuple(record.evidence_id for record in matched), evidence_status=status))

    payload = [item.model_dump(mode="json") for item in bound]
    binding_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    count = len(bound)
    return EvidenceBindingResult(
        evaluation_hash=result.evaluation_hash,
        finding_count=count,
        evidenced_count=evidenced_count,
        verified_count=verified_count,
        coverage_ratio=round(evidenced_count / count, 6) if count else 1.0,
        findings=tuple(bound),
        binding_hash=binding_hash,
    )
