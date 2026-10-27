from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChangedNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    changed_fields: tuple[str, ...] = ()


class RegulatoryInvalidation(BaseModel):
    model_config = ConfigDict(frozen=True)

    target: str
    status: Literal["stale", "unaffected"]
    reasons: tuple[str, ...]
    source_node_ids: tuple[str, ...]


class RegulatoryImpactResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    revision_id: str
    invalidations: tuple[RegulatoryInvalidation, ...]
    impacted_targets: tuple[str, ...]
    impact_hash: str


_TARGETS = ("regulatory-findings", "regulatory-evidence", "regulatory-verification")


def _reasons(node: ChangedNode) -> tuple[str, ...]:
    kind = node.artifact_type.lower()
    fields = {field.lower() for field in node.changed_fields}
    reasons: list[str] = []
    if kind in {"canonical-model", "model", "project"}:
        reasons.append("canonical-model-changed")
    if kind in {"geometry", "wall", "door", "window", "slab", "space", "level"}:
        reasons.append("spatial-facts-changed")
    if kind in {"requirement", "requirements", "assumption", "decision", "site"}:
        reasons.append("regulatory-context-changed")
    if kind in {"rule-pack", "regulatory-rule-pack", "regulatory"}:
        reasons.append("rule-pack-changed")
    if kind in {"evidence", "regulatory-evidence"}:
        reasons.append("evidence-state-changed")
    if {"building_type", "occupancy", "location", "jurisdiction", "region"} & fields:
        reasons.append("applicability-context-changed")
    return tuple(dict.fromkeys(reasons))


def calculate_regulatory_impact(revision_id: str, changed_nodes: tuple[ChangedNode, ...]) -> RegulatoryImpactResult:
    reasons: list[str] = []
    source_ids: list[str] = []
    for node in changed_nodes:
        reasons.extend(_reasons(node))
        if _reasons(node):
            source_ids.append(node.node_id)

    unique_reasons = tuple(dict.fromkeys(reasons))
    stale = bool(unique_reasons)
    invalidations = tuple(
        RegulatoryInvalidation(target=target, status="stale" if stale else "unaffected", reasons=unique_reasons, source_node_ids=tuple(source_ids))
        for target in _TARGETS
    )
    impacted = tuple(item.target for item in invalidations if item.status == "stale")
    payload = [item.model_dump(mode="json") for item in invalidations]
    impact_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return RegulatoryImpactResult(
        revision_id=revision_id,
        invalidations=invalidations,
        impacted_targets=impacted,
        impact_hash=impact_hash,
    )
