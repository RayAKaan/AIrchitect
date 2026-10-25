from app.domains.commands.preconditions import check_preconditions


def test_missing_element_fails_closed():
    command = type("C", (), {"type": "MoveBuilding", "payload": {"element_id": "missing"}})()
    assert check_preconditions({"semantic_model": {"elements": []}}, {"locks": {}}, command) == ["SEMANTIC_ELEMENT_NOT_FOUND"]


def test_locked_element_is_not_mutable():
    command = type("C", (), {"type": "MoveBuilding", "payload": {"element_id": "b"}})()
    model = {"semantic_model": {"elements": [{"id": "b", "type": "Building"}]}}
    state = {"locks": {"b": {"locked": True}}}
    assert "SEMANTIC_ELEMENT_LOCKED" in check_preconditions(model, state, command)
