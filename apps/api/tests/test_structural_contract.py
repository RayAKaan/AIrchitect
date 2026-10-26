import pytest

from app.domains.engineering.structural_contract import StructuralInputContract, require_structural_inputs


def test_structural_contract_accepts_complete_inputs() -> None:
    require_structural_inputs(StructuralInputContract("g", "q", "w", "d"))


@pytest.mark.parametrize("values", [("", "q", "w", "d"), ("g", "", "w", "d"), ("g", "q", "", "d"), ("g", "q", "w", "")])
def test_structural_contract_rejects_incomplete_inputs(values) -> None:
    with pytest.raises(ValueError, match="STRUCTURAL_INPUTS_INVALID"):
        require_structural_inputs(StructuralInputContract(*values))
