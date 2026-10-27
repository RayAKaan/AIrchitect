from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RuleCheckType = Literal["required", "boolean", "numeric_min", "numeric_max", "enum"]


class RuleApplicability(BaseModel):
    model_config = ConfigDict(frozen=True)

    building_types: tuple[str, ...] = ()
    occupancies: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()

    def matches(self, context: dict[str, Any]) -> bool:
        for key, allowed in (("building_type", self.building_types), ("occupancy", self.occupancies), ("region", self.regions)):
            if allowed and context.get(key) not in allowed:
                return False
        return True


class RuleDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=240)
    subject: str = Field(min_length=1, max_length=240)
    check_type: RuleCheckType
    expected: Any = None
    unit: str | None = None
    severity: Literal["info", "warning", "error"] = "error"
    applicability: RuleApplicability = Field(default_factory=RuleApplicability)
    source_refs: tuple[str, ...] = Field(min_length=1)


class RulePack(BaseModel):
    model_config = ConfigDict(frozen=True)

    pack_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    effective_date: date | None = None
    status: Literal["catalog_only", "executable"] = "executable"
    source_refs: tuple[str, ...] = Field(min_length=1)
    rules: tuple[RuleDefinition, ...] = ()

    @model_validator(mode="after")
    def validate_unique_rules(self) -> "RulePack":
        ids = [rule.rule_id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Rule IDs must be unique within a rule pack")
        if self.status == "executable" and not self.rules:
            raise ValueError("Executable rule packs must contain at least one rule")
        return self

    @property
    def pack_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude_none=True)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


SBC_2024_CATALOG = RulePack(
    pack_id="saudi-building-code-2024-catalog",
    profile_id="saudi-arabia",
    version="2024",
    effective_date=date(2024, 1, 1),
    status="catalog_only",
    source_refs=(
        "https://sbc.gov.sa/en/BC/Pages/BuildingCode/BC.aspx?year=2024",
        "https://sbc.gov.sa/en/BC/Pages/BuildingCode/BCDetails.aspx?codeId=201&year=2024",
    ),
)


_CATALOG: tuple[RulePack, ...] = (SBC_2024_CATALOG,)


def list_rule_packs() -> tuple[RulePack, ...]:
    return _CATALOG


def get_rule_pack(pack_id: str) -> RulePack | None:
    return next((pack for pack in _CATALOG if pack.pack_id == pack_id), None)
