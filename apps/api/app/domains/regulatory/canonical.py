from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from shapely.geometry import Polygon

from app.domains.model import ArchitecturalModel, model_hash
from .checks import FactValue, evaluate_rule_pack
from .evidence import EvidenceRecord, bind_evidence
from .impact import calculate_regulatory_impact
from .rulepacks import RulePack
from .verification import verify_regulatory_state


class CanonicalRegulatoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack: RulePack
    context: dict[str, Any] = Field(default_factory=dict)
    supplemental_facts: dict[str, FactValue] = Field(default_factory=dict)
    evidence_records: tuple[EvidenceRecord, ...] = ()

    @model_validator(mode="after")
    def validate_evidence_and_sources(self) -> "CanonicalRegulatoryRequest":
        if self.pack.status != "executable":
            raise ValueError("Catalog-only rule packs cannot be executed")
        allowed_sources = set(self.pack.source_refs)
        if not allowed_sources or any(not ref.startswith("https://") for ref in allowed_sources):
            raise ValueError("Executable rule pack sources must be HTTPS references")
        for rule in self.pack.rules:
            if not set(rule.source_refs).issubset(allowed_sources):
                raise ValueError(f"Rule {rule.rule_id} references a source outside the pack manifest")
        record_sources = [item.source_ref for item in self.evidence_records]
        if len(record_sources) != len(set(record_sources)):
            raise ValueError("Evidence source references must be unique")
        for item in self.evidence_records:
            if item.source_ref not in allowed_sources:
                raise ValueError(f"Evidence source is not in the rule pack manifest: {item.source_ref}")
            if item.verification_status == "verified":
                if not item.reviewer_ref or not item.content_digest:
                    raise ValueError("Verified evidence requires reviewer_ref and content_digest")
                if len(item.content_digest) != 64 or any(ch not in "0123456789abcdef" for ch in item.content_digest.lower()):
                    raise ValueError("Verified evidence content_digest must be a SHA-256 hex digest")
        for name, fact in self.supplemental_facts.items():
            if not fact.source_ref or not fact.source_ref.strip():
                raise ValueError(f"Supplemental fact {name} requires a source_ref")
        return self


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _canonical_facts(model: ArchitecturalModel, digest: str) -> dict[str, FactValue]:
    spaces = []
    for space in model.spaces:
        polygon = Polygon([(point.x, point.y) for point in space.boundary])
        if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
            raise ValueError(f"REGULATORY_SPACE_GEOMETRY_INVALID:{space.id}")
        spaces.append(polygon.area)
    top = max((level.elevation_m + level.height_m for level in model.levels), default=None)
    source = f"canonical-model:{digest}"
    facts: dict[str, FactValue] = {
        "site.width_m": FactValue(value=model.site.width_m, unit="m", source_ref=source),
        "site.depth_m": FactValue(value=model.site.depth_m, unit="m", source_ref=source),
        "site.area_m2": FactValue(value=round(model.site.width_m * model.site.depth_m, 6), unit="m2", source_ref=source),
        "building.level_count": FactValue(value=len(model.levels), unit="count", source_ref=source),
        "building.height_m": FactValue(value=top, unit="m", source_ref=source),
        "building.space_count": FactValue(value=len(model.spaces), unit="count", source_ref=source),
        "building.floor_area_m2": FactValue(value=round(sum(spaces), 6), unit="m2", source_ref=source),
        "building.wall_count": FactValue(value=len(model.walls), unit="count", source_ref=source),
        "building.door_count": FactValue(value=len(model.doors), unit="count", source_ref=source),
        "building.window_count": FactValue(value=len(model.windows), unit="count", source_ref=source),
        "building.stair_count": FactValue(value=len(model.stairs), unit="count", source_ref=source),
    }
    return facts


def build_canonical_regulatory_package(
    model: ArchitecturalModel,
    revision_id: str,
    request: CanonicalRegulatoryRequest,
) -> dict[str, Any]:
    """Evaluate a supplied executable rule pack against canonical facts and bind its evidence."""
    source_hash = model_hash(model)
    facts = _canonical_facts(model, source_hash)
    facts.update(request.supplemental_facts)
    result = evaluate_rule_pack(request.pack, facts, request.context)
    evidence = bind_evidence(result, request.evidence_records)
    impact = calculate_regulatory_impact(revision_id, ())
    verification = verify_regulatory_state(revision_id, result, evidence, impact)
    payload: dict[str, Any] = {
        "schema_version": "canonical-regulatory-evidence-v1",
        "source_model_hash": source_hash,
        "source_revision_id": revision_id,
        "jurisdiction_profile_id": request.pack.profile_id,
        "rule_pack": request.pack.model_dump(mode="json"),
        "rule_pack_hash": request.pack.pack_hash,
        "facts": {name: fact.model_dump(mode="json") for name, fact in sorted(facts.items())},
        "evaluation": result.model_dump(mode="json"),
        "evidence": evidence.model_dump(mode="json"),
        "impact": impact.model_dump(mode="json"),
        "verification": verification.model_dump(mode="json"),
        "summary": {
            "pass": sum(item.status == "pass" for item in result.findings),
            "fail": sum(item.status == "fail" for item in result.findings),
            "missing_input": sum(item.status == "missing_input" for item in result.findings),
            "invalid_input": sum(item.status == "invalid_input" for item in result.findings),
            "not_applicable": sum(item.status == "not_applicable" for item in result.findings),
            "evidence_verified": evidence.verified_count,
            "evidence_missing": sum(item.evidence_status == "missing" for item in evidence.findings),
        },
        "limitations": [
            "Results are a technical screening record, not legal advice, permit approval or a compliance certificate.",
            "Only the supplied executable rule pack is evaluated; catalog-only jurisdiction packs are not executable.",
            "Evidence verification is represented by supplied reviewer attestations and content digests; the service does not independently authenticate the issuing authority.",
            "Facts absent from the canonical model remain missing unless supplied with explicit source provenance.",
        ],
    }
    payload["package_hash"] = _digest(payload)
    return payload
