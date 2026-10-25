from __future__ import annotations

import re
from dataclasses import dataclass

from .intent_normalization import normalize_intent_text


@dataclass(frozen=True)
class IntentProposal:
    command_type: str | None
    payload: dict[str, object]
    confidence: float
    missing_fields: tuple[str, ...]
    ambiguous: bool


_PATTERNS = (
    (re.compile(r"\bmove\s+(?:the\s+)?building\b", re.I), "MoveBuilding"),
    (re.compile(r"\brotate\s+(?:the\s+)?building\b", re.I), "RotateBuilding"),
    (re.compile(r"\bresize\s+(?:the\s+)?space\b", re.I), "ResizeSpace"),
    (re.compile(r"\bmove\s+(?:the\s+)?space\b", re.I), "MoveSpace"),
    (re.compile(r"\bchange\s+(?:the\s+)?setback\b", re.I), "ChangeSetback"),
)

_TARGET_REQUIRED = {"MoveBuilding", "RotateBuilding", "ResizeSpace", "MoveSpace"}
_NUMBER = r"(-?(?:\d+(?:\.\d*)?|\.\d+))"


def _unique_matches(text: str) -> list[str]:
    return [command for pattern, command in _PATTERNS if pattern.search(text)]


def parse_intent(text: str) -> IntentProposal:
    normalized = normalize_intent_text(text).text
    matches = _unique_matches(normalized)
    if len(matches) != 1:
        return IntentProposal(None, {}, 0.0, (), bool(matches))

    command_type = matches[0]
    payload: dict[str, object] = {}
    missing: list[str] = []
    element_match = re.search(r"\b(?:element|id)\s*[:#]?\s*([a-z0-9_.-]+)", normalized, re.I)
    if element_match:
        payload["element_id"] = element_match.group(1)
    elif command_type in _TARGET_REQUIRED:
        missing.append("element_id")

    if command_type in {"MoveBuilding", "MoveSpace"}:
        vector = re.search(
            rf"{_NUMBER}\s*m\s*(?:x|by|,|and)\s*{_NUMBER}\s*m",
            normalized,
            re.I,
        )
        if vector:
            payload["translation_m"] = {
                "x": float(vector.group(1)),
                "y": float(vector.group(2)),
                "z": 0.0,
            }
        else:
            missing.append("translation_m")
    elif command_type == "RotateBuilding":
        angle = re.search(rf"{_NUMBER}\s*(?:deg|degree|degrees|°)", normalized, re.I)
        if angle:
            payload["angle_deg"] = float(angle.group(1))
        else:
            missing.append("angle_deg")
    elif command_type == "ResizeSpace":
        area = re.search(rf"{_NUMBER}\s*(?:m2|m²|sqm|square\s*met(?:er|re)s?)\b", normalized, re.I)
        if area:
            payload["area_m2"] = float(area.group(1))
        else:
            missing.append("area_m2")
    elif command_type == "ChangeSetback":
        setback = re.search(rf"{_NUMBER}\s*m\b", normalized, re.I)
        if setback:
            payload["setback_m"] = float(setback.group(1))
        else:
            missing.append("setback_m")

    confidence = 0.95 if not missing else 0.65
    return IntentProposal(command_type, payload, confidence, tuple(missing), False)
