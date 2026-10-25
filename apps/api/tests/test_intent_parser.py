from __future__ import annotations

from app.domains.commands.intent_parser import parse_intent


def test_parser_normalizes_case_and_whitespace() -> None:
    proposal = parse_intent("  MOVE   the BUILDING   2 m x 3 m element: b1 ")
    assert proposal.command_type == "MoveBuilding"
    assert proposal.payload == {"element_id": "b1", "translation_m": {"x": 2.0, "y": 3.0, "z": 0.0}}
    assert proposal.missing_fields == ()
    assert proposal.confidence == 0.95


def test_parser_rejects_multiple_intents() -> None:
    proposal = parse_intent("move the building 2 m x 3 m and rotate the building 10 degrees")
    assert proposal.command_type is None
    assert proposal.ambiguous is True
    assert proposal.confidence == 0.0


def test_parser_keeps_missing_fields_explicit() -> None:
    proposal = parse_intent("resize the space element:s1")
    assert proposal.command_type == "ResizeSpace"
    assert proposal.payload == {"element_id": "s1"}
    assert proposal.missing_fields == ("area_m2",)
    assert proposal.confidence == 0.65


def test_parser_accepts_decimal_quantities() -> None:
    proposal = parse_intent("rotate the building 12.5 degrees id:b1")
    assert proposal.payload == {"element_id": "b1", "angle_deg": 12.5}
