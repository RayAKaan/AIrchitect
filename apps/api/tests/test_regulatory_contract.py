import pytest

from app.domains.engineering.regulatory_contract import RegulatoryInputContract, require_regulatory_inputs


def test_regulatory_contract_accepts_complete_inputs() -> None:
    require_regulatory_inputs(RegulatoryInputContract("g", "q", "w", "d", "rules"))


@pytest.mark.parametrize("field", ["geometry_hash", "quantity_hash", "world_model_hash", "design_hash", "ruleset_hash"])
def test_regulatory_contract_rejects_missing_input(field: str) -> None:
    values = {
        "geometry_hash": "g",
        "quantity_hash": "q",
        "world_model_hash": "w",
        "design_hash": "d",
        "ruleset_hash": "rules",
    }
    values[field] = ""

    with pytest.raises(ValueError, match="REGULATORY_INPUTS_INVALID"):
        require_regulatory_inputs(RegulatoryInputContract(**values))
