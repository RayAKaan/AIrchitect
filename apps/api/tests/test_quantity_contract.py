import pytest

from app.domains.engineering.quantity_contract import QuantityInputContract, require_quantity_inputs


def test_quantity_contract_accepts_canonical_geometry() -> None:
    require_quantity_inputs(QuantityInputContract("geometry", "geometry-hash", "world-hash", "design-hash"))


@pytest.mark.parametrize("field", ["geometry_id", "geometry_hash", "world_model_hash", "design_hash"])
def test_quantity_contract_rejects_missing_dependency(field: str) -> None:
    values = {
        "geometry_id": "geometry",
        "geometry_hash": "geometry-hash",
        "world_model_hash": "world-hash",
        "design_hash": "design-hash",
    }
    values[field] = ""

    with pytest.raises(ValueError, match="QUANTITY_INPUTS_INVALID"):
        require_quantity_inputs(QuantityInputContract(**values))
