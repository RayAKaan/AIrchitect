from decimal import Decimal

import pytest

from app.domains.lifecycle.cost_derivation import derive_costs


def test_cost_derivation_is_stable_and_rounded() -> None:
    lines = derive_costs(
        [("z", Decimal("2")), ("a", Decimal("1.005"))],
        {"a": Decimal("10"), "z": Decimal("3.333")},
        currency="SAR",
    )
    assert [line.key for line in lines] == ["a", "z"]
    assert [line.amount for line in lines] == [Decimal("10.05"), Decimal("6.67")]


def test_cost_derivation_rejects_missing_rates() -> None:
    with pytest.raises(ValueError, match="missing unit rate"):
        derive_costs([("a", Decimal("1"))], {}, currency="SAR")
