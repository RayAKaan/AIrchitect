from __future__ import annotations

from app.domains.commands.intent_contract import contract_for
from app.domains.commands.intent_parser import parse_intent


def test_complete_but_unimplemented_intent_is_not_executable() -> None:
    contract = contract_for(parse_intent("move the building 2 m x 3 m id:b1"))
    assert contract.executable is False
    assert contract.reason == "command has no canonical mutation adapter yet"


def test_complete_supported_intent_is_executable() -> None:
    contract = contract_for(parse_intent("resize the space 20 m2 id:s1"))
    assert contract.executable is True
    assert contract.missing_fields == ()


def test_preview_contract_is_fail_closed_for_missing_values() -> None:
    contract = contract_for(parse_intent("resize the space id:s1"))
    assert contract.executable is False
    assert contract.missing_fields == ("area_m2",)


def test_preview_contract_is_fail_closed_for_ambiguity() -> None:
    contract = contract_for(parse_intent("move the building and rotate the building"))
    assert contract.executable is False
    assert contract.reason == "intent is ambiguous or unsupported"
