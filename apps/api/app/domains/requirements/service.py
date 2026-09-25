import re
from app.domains.requirements.schemas import Requirement, RequirementCategory as C, RequirementIssue

PATTERNS = [
    (C.FLOORS, "floor_count", r"\b(\d{1,2})\s*(?:floors?|storeys|stories)\b", None),
    (C.HEIGHT, "building_height", r"\b(\d+(?:\.\d+)?)\s*(m|meters?|metres?)\s*(?:high|height)?\b", "m"),
    (C.AREA, "target_gfa", r"\b(\d[\d,]*(?:\.\d+)?)\s*(m2|m²|sqm|sq\.?\s*m|square\s*meters?)\b", "m²"),
    (C.BUDGET, "budget", r"\b(?:sar|\u20b9)\s*([\d,]+(?:\.\d+)?)\b", "SAR"),
    (C.PARKING, "parking_spaces", r"\b(\d{1,4})\s*(?:parking\s+)?spaces\b", "spaces"),
]

def analyze_brief(brief: str):
    reqs: list[Requirement] = []
    for category, parameter, pattern, unit in PATTERNS:
        for match in re.finditer(pattern, brief, re.IGNORECASE):
            raw = match.group(1).replace(",", "")
            value: int | float = float(raw) if "." in raw else int(raw)
            if category == C.FLOORS or category == C.PARKING:
                value = int(value)
            detected_unit = unit
            if category == C.HEIGHT and len(match.groups()) > 1:
                detected_unit = "m"
            reqs.append(Requirement(category=category, parameter=parameter, value=value, unit=detected_unit, source_text=match.group(0)))
    issues: list[RequirementIssue] = []
    by_param: dict[str, set[str]] = {}
    for r in reqs:
        by_param.setdefault(r.parameter, set()).add(str(r.value))
    for parameter, values in by_param.items():
        if len(values) > 1:
            issues.append(RequirementIssue(code="CONFLICTING_VALUES", severity="warning", message=f"Multiple values detected for {parameter}; confirm the intended value.", related_parameters=[parameter]))
    if not any(r.category == C.AREA for r in reqs):
        pass
    missing = [label for label, present in [
        ("site dimensions or boundary", bool(re.search(r"\b(site|plot)\b.{0,50}\d", brief, re.I))),
        ("target gross floor area", any(r.category == C.AREA for r in reqs)),
        ("floor count or height", any(r.category in {C.FLOORS, C.HEIGHT} for r in reqs)),
        ("budget or cost constraint", any(r.category == C.BUDGET for r in reqs)),
        ("parking requirement", any(r.category == C.PARKING for r in reqs)),
    ] if not present]
    return reqs, missing, issues
