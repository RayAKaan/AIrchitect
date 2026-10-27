from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .checks import FactValue, RegulatoryCheckResult, evaluate_rule_pack
from .evidence import EvidenceBindingResult, EvidenceRecord, bind_evidence
from .rulepacks import RulePack

RegenerationTarget = Literal["regulatory-findings", "regulatory-evidence"]


class RegenerationTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    target: RegenerationTarget
    reason: str
    depends_on: tuple[RegenerationTarget, ...] = ()


class RegenerationPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    revision_id: str
    tasks: tuple[RegenerationTask, ...]
    plan_hash: str


class SelectiveRegenerationRequest(BaseModel):
    revision_id: str = Field(min_length=1)
    targets: tuple[RegenerationTarget, ...]
    pack: RulePack | None = None
    facts: dict[str, FactValue | str | float | int | bool | None] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    existing_result: RegulatoryCheckResult | None = None
    evidence_records: tuple[EvidenceRecord, ...] = ()


class RegenerationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    revision_id: str
    executed_targets: tuple[RegenerationTarget, ...]
    skipped_targets: tuple[RegenerationTarget, ...]
    findings: RegulatoryCheckResult | None = None
    evidence: EvidenceBindingResult | None = None
    execution_hash: str


def build_regeneration_plan(revision_id: str, targets: tuple[RegenerationTarget, ...], reasons: dict[str, str] | None = None) -> RegenerationPlan:
    reasons = reasons or {}
    ordered = tuple(dict.fromkeys(targets))
    tasks = tuple(
        RegenerationTask(
            target=target,
            reason=reasons.get(target, "requested-selective-regeneration"),
            depends_on=("regulatory-findings",) if target == "regulatory-evidence" else (),
        )
        for target in ordered
    )
    payload = [task.model_dump(mode="json") for task in tasks]
    plan_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return RegenerationPlan(revision_id=revision_id, tasks=tasks, plan_hash=plan_hash)


def execute_selective_regeneration(request: SelectiveRegenerationRequest) -> RegenerationResult:
    requested = tuple(dict.fromkeys(request.targets))
    findings = request.existing_result
    evidence: EvidenceBindingResult | None = None
    executed: list[RegenerationTarget] = []

    if "regulatory-findings" in requested:
        if request.pack is None:
            raise ValueError("A rule pack is required to regenerate regulatory findings")
        findings = evaluate_rule_pack(request.pack, request.facts, request.context)
        executed.append("regulatory-findings")

    if "regulatory-evidence" in requested:
        if findings is None:
            raise ValueError("Regulatory evidence regeneration requires findings or an existing result")
        evidence = bind_evidence(findings, request.evidence_records)
        executed.append("regulatory-evidence")

    skipped = tuple(target for target in requested if target not in executed)
    payload = {
        "revision_id": request.revision_id,
        "executed_targets": executed,
        "skipped_targets": skipped,
        "findings_hash": findings.evaluation_hash if findings else None,
        "evidence_hash": evidence.binding_hash if evidence else None,
    }
    execution_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return RegenerationResult(
        revision_id=request.revision_id,
        executed_targets=tuple(executed),
        skipped_targets=skipped,
        findings=findings,
        evidence=evidence,
        execution_hash=execution_hash,
    )
