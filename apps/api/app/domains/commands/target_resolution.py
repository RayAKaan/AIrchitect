from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TargetResolution:
    element_id: str | None
    ambiguous: bool
    reason: str | None = None


def _normalize_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def resolve_target(model: dict[str, Any], *, element_id: str | None = None, name: str | None = None, expected_type: str | None = None) -> TargetResolution:
    """Resolve exact identifiers or normalized exact names; never fuzzy-match."""
    semantic = model.get("semantic_model")
    elements = semantic.get("elements", []) if isinstance(semantic, dict) else []
    if element_id:
        for element in elements:
            if element.get("id") == element_id and (expected_type is None or element.get("type") == expected_type):
                return TargetResolution(element_id, False)
        return TargetResolution(None, False, "target id not found")
    if not name:
        return TargetResolution(None, False, "target identifier is required")
    normalized_name = _normalize_name(name)
    matches = [
        element for element in elements
        if isinstance(element.get("name"), str)
        and _normalize_name(element["name"]) == normalized_name
        and (expected_type is None or element.get("type") == expected_type)
    ]
    if len(matches) == 1:
        return TargetResolution(matches[0].get("id"), False)
    if len(matches) > 1:
        return TargetResolution(None, True, "target name is ambiguous")
    return TargetResolution(None, False, "target name not found")
