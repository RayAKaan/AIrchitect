import pytest

from app.domains.ai.copilot_impact import explain_impact_groups


def test_impact_explanations_are_deterministic_and_deduplicated() -> None:
    explanations = explain_impact_groups(["cost", "quantities", "cost"])

    assert [item.group for item in explanations] == ["cost", "quantities"]
    assert explanations[0].artifact_type == "cost"
    assert explanations[1].regeneration_required is True


def test_unknown_impact_group_fails_closed() -> None:
    with pytest.raises(ValueError, match="UNKNOWN_IMPACT_GROUP"):
        explain_impact_groups(["not-a-real-impact"])
