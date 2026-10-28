from __future__ import annotations

from app.domains.commands.intent_contract import contract_for
from app.domains.commands.intent_parser import IntentProposal


def test_complete_registered_intent_is_executable() -> None:
    contract = contract_for(IntentProposal("MoveBuilding", {"element_id": "b1", "translation_m": {"x": 1, "y": 2, "z": 0}}, 0.95, (), False))
    assert contract.executable is True
    assert contract.missing_fields == ()


def test_partial_intent_uses_server_requirement_registry() -> None:
    contract = contract_for(IntentProposal("ResizeSpace", {"element_id": "s1"}, 0.65, ("area_m2",), False))
    assert contract.executable is False
    assert contract.missing_fields == ("area_m2",)


def test_ambiguous_intent_can_never_be_executable() -> None:
    contract = contract_for(IntentProposal(None, {}, 0.0, (), True))
    assert contract.executable is False
    assert contract.reason is not None
