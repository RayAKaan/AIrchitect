from fastapi import APIRouter, HTTPException

from .rulepacks import RulePack, get_rule_pack, list_rule_packs

router = APIRouter(prefix="/regulatory/rule-packs", tags=["regulatory-rule-packs"])


@router.get("", response_model=list[RulePack])
async def rule_packs() -> list[RulePack]:
    return list(list_rule_packs())


@router.get("/{pack_id}", response_model=RulePack)
async def rule_pack(pack_id: str) -> RulePack:
    value = get_rule_pack(pack_id)
    if value is None:
        raise HTTPException(404, "Regulatory rule pack not found")
    return value
