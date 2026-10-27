from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .profiles import get_profile, list_profiles

router = APIRouter(prefix="/regulatory/profiles", tags=["regulatory-profiles"])


class JurisdictionProfileOut(BaseModel):
    profile_id: str = Field(min_length=1)
    name: str
    country_code: str
    authority: str
    code_family: str
    default_unit_system: str
    status: str


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


@router.get("", response_model=list[JurisdictionProfileOut])
async def profiles() -> list[JurisdictionProfileOut]:
    return [_serialize(profile) for profile in list_profiles()]


@router.get("/{profile_id}", response_model=JurisdictionProfileOut)
async def profile(profile_id: str) -> JurisdictionProfileOut:
    value = get_profile(profile_id)
    if value is None:
        raise HTTPException(404, "Jurisdiction profile not found")
    return _serialize(value)
