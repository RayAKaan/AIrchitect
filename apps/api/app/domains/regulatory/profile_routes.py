from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .checks import FactValue, RegulatoryCheckResult, evaluate_rule_pack
from .evidence import EvidenceBindingResult, EvidenceRecord, bind_evidence
from .impact import ChangedNode, RegulatoryImpactResult, calculate_regulatory_impact
from .profiles import get_profile, list_profiles
from .regeneration import RegenerationResult, SelectiveRegenerationRequest, execute_selective_regeneration
from .rulepacks import RulePack, get_rule_pack, list_rule_packs
from .verification import RegulatoryVerification, verify_regulatory_state

router = APIRouter(tags=["regulatory"])


class JurisdictionProfileOut(BaseModel):
    profile_id: str = Field(min_length=1)
    name: str
    country_code: str
    authority: str
    code_family: str
    default_unit_system: str
    status: str


class RegulatoryCheckRequest(BaseModel):
    pack: RulePack
    facts: dict[str, FactValue | str | float | int | bool | None]
    context: dict[str, Any] = Field(default_factory=dict)


class EvidenceBindingRequest(BaseModel):
    result: RegulatoryCheckResult
    records: tuple[EvidenceRecord, ...] = ()


class RegulatoryImpactRequest(BaseModel):
    revision_id: str = Field(min_length=1)
    changed_nodes: tuple[ChangedNode, ...]


class RegulatoryVerificationRequest(BaseModel):
    revision_id: str = Field(min_length=1)
    check_result: RegulatoryCheckResult
    evidence: EvidenceBindingResult
    impact: RegulatoryImpactResult
    regeneration: RegenerationResult | None = None


def _serialize(profile) -> JurisdictionProfileOut:
    return JurisdictionProfileOut(**profile.__dict__) if hasattr(profile, "__dict__") else JurisdictionProfileOut(
        profile_id=profile.profile_id,
        name=profile.name,
        country_code=profile.country_code,
        authority=profile.authority,
        code_family=profile.code_family,
        default_unit_system=profile.default_unit_system,
        status=profile.status,
    )


@router.get("/regulatory/profiles", response_model=list[JurisdictionProfileOut])
async def profiles() -> list[JurisdictionProfileOut]:
    return [_serialize(profile) for profile in list_profiles()]


@router.get("/regulatory/profiles/{profile_id}", response_model=JurisdictionProfileOut)
async def profile(profile_id: str) -> JurisdictionProfileOut:
    value = get_profile(profile_id)
    if value is None:
        raise HTTPException(404, "Jurisdiction profile not found")
    return _serialize(value)


@router.get("/regulatory/rule-packs", response_model=list[RulePack])
async def rule_packs() -> list[RulePack]:
    return list(list_rule_packs())


@router.get("/regulatory/rule-packs/{pack_id}", response_model=RulePack)
async def rule_pack(pack_id: str) -> RulePack:
    value = get_rule_pack(pack_id)
    if value is None:
        raise HTTPException(404, "Regulatory rule pack not found")
    return value


@router.post("/regulatory/checks", response_model=RegulatoryCheckResult)
async def regulatory_checks(body: RegulatoryCheckRequest) -> RegulatoryCheckResult:
    try:
        return evaluate_rule_pack(body.pack, body.facts, body.context)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/regulatory/evidence/bind", response_model=EvidenceBindingResult)
async def regulatory_evidence(body: EvidenceBindingRequest) -> EvidenceBindingResult:
    return bind_evidence(body.result, body.records)


@router.post("/regulatory/impact", response_model=RegulatoryImpactResult)
async def regulatory_impact(body: RegulatoryImpactRequest) -> RegulatoryImpactResult:
    return calculate_regulatory_impact(body.revision_id, body.changed_nodes)


@router.post("/regulatory/regenerate", response_model=RegenerationResult)
async def regulatory_regenerate(body: SelectiveRegenerationRequest) -> RegenerationResult:
    try:
        return execute_selective_regeneration(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/regulatory/verify", response_model=RegulatoryVerification)
async def regulatory_verify(body: RegulatoryVerificationRequest) -> RegulatoryVerification:
    return verify_regulatory_state(body.revision_id, body.check_result, body.evidence, body.impact, body.regeneration)
