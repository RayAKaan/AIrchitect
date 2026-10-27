import pytest

from app.domains.engineering.load_combinations import LoadCase, build_default_combinations


def test_default_combinations_are_explicit():
    combinations = build_default_combinations((LoadCase("dead", "dead", 1.5), LoadCase("live", "live", 2.0)))
    assert combinations[0].label == "1.2D + 1.6L"
    assert combinations[0].factors == (("dead", 1.2), ("live", 1.6))
    assert combinations[1].label == "D + L"


def test_missing_case_is_rejected():
    with pytest.raises(ValueError, match="LOAD_COMBINATION_INPUTS_INVALID"):
        build_default_combinations((LoadCase("dead", "dead", 1.5),))
