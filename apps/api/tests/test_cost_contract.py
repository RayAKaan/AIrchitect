import pytest

from app.domains.engineering.cost_contract import CostInputContract, require_cost_inputs


def test_cost_contract_accepts_quantity_and_rate_schedule() -> None:
    require_cost_inputs(CostInputContract("quantity-hash", "rate-schedule-hash", "SAR"))


@pytest.mark.parametrize("field", ["quantity_hash", "rate_schedule_hash", "currency"])
def test_cost_contract_rejects_missing_input(field: str) -> None:
    values = {"quantity_hash": "quantity-hash", "rate_schedule_hash": "rate-hash", "currency": "SAR"}
    values[field] = ""

    with pytest.raises(ValueError, match="COST_INPUTS_INVALID"):
        require_cost_inputs(CostInputContract(**values))
