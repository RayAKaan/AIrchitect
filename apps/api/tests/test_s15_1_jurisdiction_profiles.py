from app.domains.regulatory.profiles import get_profile, list_profiles


def test_profiles_are_deterministic_and_include_neutral_and_saudi_context():
    first = list_profiles()
    second = list_profiles()
    assert first == second
    assert get_profile("jurisdiction-neutral").code_family == "none"
    assert get_profile("saudi-arabia").country_code == "SA"
    assert get_profile("saudi-arabia").status == "rule_pack_required"


def test_unknown_profile_is_not_synthesized():
    assert get_profile("does-not-exist") is None
