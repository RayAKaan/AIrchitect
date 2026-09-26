from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RequirementCandidate:
    category: str
    parameter: str
    raw_value: Any
    normalized_value: Any
    unit: str | None
    source_text: str
    value_type: str
    confidence: float
    extraction_method: str = "deterministic_pattern_v3"


class RequirementExtractor(Protocol):
    def extract(self, brief: str) -> list[RequirementCandidate]: ...


class DeterministicRequirementExtractor:
    """Conservative MVP extractor. It emits only facts with explicit deterministic evidence."""

    _quantity_units = r"(?:m2|m²|sqm|sq\.?\s*m|square\s*met(?:er|re)s?)"

    def extract(self, brief: str) -> list[RequirementCandidate]:
        candidates: list[RequirementCandidate] = []

        def add(category: str, parameter: str, match: re.Match[str], value: Any, unit: str | None,
                value_type: str, confidence: float = 1.0) -> None:
            candidates.append(RequirementCandidate(category, parameter, match.group(1), value, unit,
                match.group(0), value_type, confidence))

        number_words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
        floor_pattern = r"\b(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[ -]*(?:floors?|storeys|stories)\b"
        for match in re.finditer(floor_pattern, brief, re.I):
            raw = match.group(1).lower()
            add("floor", "floor_count", match, number_words.get(raw, int(raw) if raw.isdigit() else 0), "count", "integer")

        site_patterns = [
            rf"\b(?:site|plot)(?:\s+area)?[^\d]{{0,25}}(\d[\d,]*(?:\.\d+)?)\s*({self._quantity_units})",
            rf"\b(\d[\d,]*(?:\.\d+)?)\s*({self._quantity_units})\s+(?:site|plot)\b",
        ]
        for pattern in site_patterns:
            for match in re.finditer(pattern, brief, re.I):
                add("site", "site_area", match, float(match.group(1).replace(",", "")), "m2", "decimal")

        gfa_patterns = [
            rf"\b(?:target\s+|approximately\s+|approx\.?\s+)?(?:gfa|gross floor area)\s*(?:of|:)?\s*(\d[\d,]*(?:\.\d+)?)\s*({self._quantity_units})",
            rf"\b(\d[\d,]*(?:\.\d+)?)\s*({self._quantity_units})\s*(?:target\s+)?(?:gfa|gross floor area)\b",
        ]
        for pattern in gfa_patterns:
            for match in re.finditer(pattern, brief, re.I):
                add("area", "target_gfa", match, float(match.group(1).replace(",", "")), "m2", "decimal")

        # Backward-compatible generic area extraction only when it is not explicitly site/GFA qualified.
        if not any(c.parameter == "target_gfa" for c in candidates):
            for match in re.finditer(rf"\b(\d[\d,]*(?:\.\d+)?)\s*({self._quantity_units})\b", brief, re.I):
                if not re.search(r"(?:site|plot)", match.group(0), re.I):
                    add("area", "target_gfa", match, float(match.group(1).replace(",", "")), "m2", "decimal", .8)
                    break

        for match in re.finditer(r"(?:floor[- ]to[- ]floor|floor height)[^\d]{0,20}(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\b", brief, re.I):
            add("height", "floor_to_floor_height", match, float(match.group(1)), "m", "decimal")
        for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\s*(?:high|height)\b", brief, re.I):
            add("height", "building_height", match, float(match.group(1)), "m", "decimal")

        for city in ("Riyadh", "Jeddah", "Dammam", "Mecca", "Medina", "Bengaluru"):
            match = re.search(rf"\b({re.escape(city)})\b", brief, re.I)
            if match:
                add("location", "city", match, city, None, "string")
                break

        use_match = re.search(r"\b(commercial\s+retail|retail|commercial|office)\b", brief, re.I)
        if use_match:
            normalized = "commercial_retail" if "retail" in use_match.group(1).lower() else use_match.group(1).lower()
            add("use", "building_use", use_match, normalized, None, "enum")

        parking_match = re.search(r"\b(basement|surface|podium)\s+parking\b", brief, re.I)
        if parking_match:
            add("parking", "parking_arrangement", parking_match, parking_match.group(1).lower(), None, "enum")
        for match in re.finditer(r"\b(\d{1,5})\s*(?:parking\s+)?spaces\b", brief, re.I):
            add("parking", "parking_spaces", match, int(match.group(1)), "count", "integer")

        for match in re.finditer(r"\b(?:SAR|﷼)\s*([\d,]+(?:\.\d+)?)\b", brief, re.I):
            add("budget", "budget", match, float(match.group(1).replace(",", "")), "SAR", "decimal")

        # Stable order and exact duplicate removal.
        unique: dict[tuple[str, str, str], RequirementCandidate] = {}
        for candidate in candidates:
            unique[(candidate.parameter, str(candidate.normalized_value), candidate.source_text.lower())] = candidate
        return sorted(unique.values(), key=lambda c: (c.parameter, c.source_text.lower()))
