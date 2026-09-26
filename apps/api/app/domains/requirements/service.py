from app.domains.requirements.extractor import DeterministicRequirementExtractor, RequirementExtractor
from app.domains.requirements.schemas import Requirement, RequirementCategory as C, RequirementIssue

CATEGORY_MAP = {
    "site": C.SITE, "location": C.SITE, "building": C.BUILDING_TYPE, "use": C.BUILDING_TYPE,
    "area": C.AREA, "height": C.HEIGHT, "floor": C.FLOORS, "parking": C.PARKING,
    "budget": C.BUDGET, "schedule": C.TIMELINE,
}


def analyze_brief(brief: str, extractor: RequirementExtractor | None = None):
    provider = extractor or DeterministicRequirementExtractor()
    candidates = provider.extract(brief)
    requirements = [Requirement(category=CATEGORY_MAP.get(c.category, C.BUILDING_TYPE), parameter=c.parameter,
        value=c.normalized_value, unit=c.unit, source_text=c.source_text,
        source_type="user_brief", confirmation_status="unconfirmed") for c in candidates]
    values: dict[str, set[str]] = {}
    for candidate in candidates:
        values.setdefault(candidate.parameter, set()).add(str(candidate.normalized_value))
    issues = [RequirementIssue(code="CONFLICTING_VALUES", severity="warning",
        message=f"Multiple values detected for {parameter}; confirm the intended value.",
        related_parameters=[parameter]) for parameter, found in values.items() if len(found) > 1]
    present = {candidate.parameter for candidate in candidates}
    missing = [label for label, key_set in [
        ("site dimensions or boundary", {"site_area", "site_width", "site_depth"}),
        ("target gross floor area", {"target_gfa"}),
        ("floor count or height", {"floor_count", "building_height"}),
        ("budget or cost constraint", {"budget"}),
        ("parking requirement", {"parking_spaces", "parking_arrangement"}),
    ] if not present.intersection(key_set)]
    return requirements, missing, issues
