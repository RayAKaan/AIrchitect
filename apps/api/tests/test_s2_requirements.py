from app.domains.requirements.service import analyze_brief


def test_requirement_extraction_keeps_missing_information_explicit():
    requirements, missing, issues = analyze_brief("Design a 5 floor office building on a 2000 sqm site.")
    parameters = {item.parameter for item in requirements}
    assert "floor_count" in parameters
    assert "site_area" in parameters
    assert "budget or cost constraint" in missing
    assert "parking requirement" in missing
    assert issues == []


def test_requirement_conflicts_are_not_silently_resolved():
    _, _, issues = analyze_brief("The building should be 4 floors and 8 floors, with a 1000 sqm site.")
    assert any(issue.code == "CONFLICTING_VALUES" for issue in issues)
