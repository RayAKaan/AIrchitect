from __future__ import annotations

import pytest

from app.domains.commands.intent_normalization import normalize_intent_text


def test_normalization_is_case_and_whitespace_stable() -> None:
    result = normalize_intent_text("  Move   THE\u00a0building  ")
    assert result.text == "move the building"
    assert result.tokens == ("move", "the", "building")


def test_normalization_preserves_meaningful_hyphenated_text() -> None:
    result = normalize_intent_text("Setback\u2013east  3m")
    assert result.text == "setback-east 3m"


def test_blank_text_fails_closed() -> None:
    with pytest.raises(ValueError):
        normalize_intent_text("   ")


def test_non_string_input_is_rejected() -> None:
    with pytest.raises(TypeError):
        normalize_intent_text(None)  # type: ignore[arg-type]
