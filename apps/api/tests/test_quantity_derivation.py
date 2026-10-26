from decimal import Decimal

import pytest

from app.domains.lifecycle.quantity_derivation import derive_space_areas


def test_space_quantities_are_stable_and_sorted() -> None:
    lines = derive_space_areas({"z": {"area_m2": 2}, "a": {"area_m2": "3.50"}})
    assert [line.key for line in lines] == ["space:a:area", "space:z:area"]
    assert [line.quantity for line in lines] == [Decimal("3.50"), Decimal("2")]


def test_negative_area_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        derive_space_areas({"bad": {"area_m2": -1}})
