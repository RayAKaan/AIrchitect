from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedIntentText:
    text: str
    tokens: tuple[str, ...]


_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[\u2010-\u2015\u2212]")


def normalize_intent_text(text: str) -> NormalizedIntentText:
    """Normalize user language without changing architectural meaning.

    This is intentionally lexical: it does not infer entities, quantities, units,
    or commands. Semantic interpretation remains the responsibility of the parser.
    """
    if not isinstance(text, str):
        raise TypeError("intent text must be a string")
    normalized = text.strip()
    if not normalized:
        raise ValueError("intent text must not be blank")
    normalized = normalized.replace("\u00a0", " ")
    normalized = _PUNCTUATION.sub("-", normalized)
    normalized = _WHITESPACE.sub(" ", normalized)
    normalized = normalized.casefold()
    return NormalizedIntentText(normalized, tuple(normalized.split(" ")))
