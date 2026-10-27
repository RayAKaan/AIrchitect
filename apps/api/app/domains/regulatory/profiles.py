from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JurisdictionProfile:
    """Immutable identity for a regulatory jurisdiction.

    A profile identifies the legal/code context; it does not itself establish
    compliance. Rules and evidence must be supplied by a versioned rule pack.
    """

    profile_id: str
    name: str
    country_code: str
    authority: str
    code_family: str
    default_unit_system: str = "metric"
    status: str = "framework_only"


_PROFILES: tuple[JurisdictionProfile, ...] = (
    JurisdictionProfile(
        profile_id="jurisdiction-neutral",
        name="Jurisdiction-neutral screening",
        country_code="ZZ",
        authority="Not applicable",
        code_family="none",
    ),
    JurisdictionProfile(
        profile_id="saudi-arabia",
        name="Saudi Arabia",
        country_code="SA",
        authority="Saudi Building Code / competent authority",
        code_family="SBC",
        status="rule_pack_required",
    ),
)

_BY_ID = {profile.profile_id: profile for profile in _PROFILES}


def list_profiles() -> tuple[JurisdictionProfile, ...]:
    return _PROFILES


def get_profile(profile_id: str) -> JurisdictionProfile | None:
    return _BY_ID.get(profile_id)
