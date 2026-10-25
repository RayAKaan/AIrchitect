from __future__ import annotations

from app.domains.commands.target_resolution import resolve_target


def model() -> dict[str, object]:
    return {"semantic_model": {"elements": [
        {"id": "b1", "type": "Building", "name": "Main Block"},
        {"id": "s1", "type": "Space", "name": "Lobby"},
        {"id": "s2", "type": "Space", "name": "Lobby"},
    ]}}


def test_exact_id_is_preferred_and_type_checked() -> None:
    result = resolve_target(model(), element_id="b1", expected_type="Building")
    assert result.element_id == "b1"
    assert result.ambiguous is False


def test_unique_exact_name_resolves() -> None:
    result = resolve_target(model(), name="Main Block", expected_type="Building")
    assert result.element_id == "b1"


def test_duplicate_name_fails_closed() -> None:
    result = resolve_target(model(), name="Lobby", expected_type="Space")
    assert result.element_id is None
    assert result.ambiguous is True


def test_missing_identifier_fails_closed() -> None:
    result = resolve_target(model())
    assert result.element_id is None
    assert result.reason == "target identifier is required"
