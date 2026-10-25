from __future__ import annotations

from app.domains.commands.intent_parser import parse_intent


def test_parser_extracts_explicit_target_name_for_contextual_resolution() -> None:
    proposal = parse_intent("move the building named Main Block by 2 m x 3 m")
    assert proposal.command_type == "MoveBuilding"
    assert proposal.payload["target_name"] == "main block"
    assert proposal.missing_fields == ()
