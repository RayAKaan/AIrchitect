from app.domains.commands.intent_parser import parse_intent


def test_parse_move_intent_without_inventing_target():
    result = parse_intent("move the building 3 m x 2 m")
    assert result.command_type == "MoveBuilding"
    assert result.payload["translation_m"] == {"x": 3.0, "y": 2.0, "z": 0.0}
    assert result.missing_fields == ("element_id",)
    assert result.confidence < 1


def test_ambiguous_intent_fails_closed():
    result = parse_intent("move the building and rotate the building")
    assert result.command_type is None
    assert result.ambiguous
