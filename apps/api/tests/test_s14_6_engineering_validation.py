from app.domains.engineering.screening_validation import validate_screening_model


def test_valid_screening_result():
    result = validate_screening_model(member_count=3, total_factored_load_kn=100, model_hash="a" * 64)
    assert result.status == "SCREENING_VALID"
    assert result.findings == ()


def test_invalid_screening_result_is_explicit():
    result = validate_screening_model(member_count=0, total_factored_load_kn=-1, model_hash="a" * 64)
    assert result.status == "INVALID"
    assert {finding.code for finding in result.findings} == {"NO_STRUCTURAL_MEMBERS", "NEGATIVE_LOAD"}
