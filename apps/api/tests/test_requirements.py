from app.domains.requirements.service import analyze_brief


def test_extracts_floor_area_budget_and_parking():
    reqs, missing, issues = analyze_brief("Retail building with 3 floors, 2,400 sqm, SAR 5,000,000 and 80 parking spaces.")
    values = {r.parameter: r.value for r in reqs}
    assert values["floor_count"] == 3
    assert values["target_gfa"] == 2400
    assert values["budget"] == 5000000
    assert values["parking_spaces"] == 80
    assert not issues
    assert all(requirement.extraction_method == "deterministic_pattern_v3" for requirement in reqs)
    assert all(0.0 <= requirement.confidence <= 1.0 for requirement in reqs)


def test_ambiguous_area_extraction_preserves_lower_confidence():
    requirements, _, _ = analyze_brief("A proposed building with approximately 2400 sqm.")
    area = next(requirement for requirement in requirements if requirement.parameter == "target_gfa")
    assert area.confidence == 0.8
    assert area.extraction_method == "deterministic_pattern_v3"
    assert area.confirmation_status == "unconfirmed"


def test_conflicting_values_are_flagged():
    reqs, _, issues = analyze_brief("Building has 3 floors and later 5 floors.")
    assert len([r for r in reqs if r.parameter == "floor_count"]) == 2
    assert any(i.code == "CONFLICTING_VALUES" for i in issues)


def test_missing_inputs_are_explicit():
    _, missing, _ = analyze_brief("A commercial retail building is proposed for the site.")
    assert "target gross floor area" in missing
    assert "parking requirement" in missing
