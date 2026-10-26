import pytest

from app.domains.cad.validation_contract import CadValidationContract, require_validated_cad_run


def test_validated_cad_contract_is_accepted() -> None:
    contract = CadValidationContract(
        run_status="SUCCEEDED",
        validation={"valid": True, "checks": [{"code": "solid_valid", "status": "PASS"}], "errors": []},
    )
    assert contract.valid
    require_validated_cad_run(contract)


@pytest.mark.parametrize(
    ("status", "validation", "code"),
    [
        ("FAILED", {"valid": True, "checks": [], "errors": []}, "CAD_RUN_INVALID"),
        ("SUCCEEDED", {"valid": False, "checks": [], "errors": []}, "CAD_VALIDATION_REQUIRED"),
        ("SUCCEEDED", {"valid": True, "errors": []}, "CAD_VALIDATION_INCOMPLETE"),
        ("SUCCEEDED", {"valid": True, "checks": [], "errors": ["bad_solid"]}, "CAD_VALIDATION_FAILED"),
    ],
)
def test_invalid_cad_evidence_fails_closed(status, validation, code) -> None:
    with pytest.raises(ValueError, match=code):
        require_validated_cad_run(CadValidationContract(status, validation))
