import pytest

from app.domains.engineering.dependency_contract import EngineeringDependency, require_canonical_engineering_chain


def test_complete_engineering_chain_is_accepted() -> None:
    require_canonical_engineering_chain(
        EngineeringDependency("geometry", "geometry-hash", "quantity-hash", "structural-hash", "regulatory-hash")
    )


@pytest.mark.parametrize("field", ["geometry_id", "geometry_hash", "quantity_hash", "structural_input_hash", "regulatory_input_hash"])
def test_engineering_chain_rejects_missing_dependency(field: str) -> None:
    values = {
        "geometry_id": "geometry",
        "geometry_hash": "geometry-hash",
        "quantity_hash": "quantity-hash",
        "structural_input_hash": "structural-hash",
        "regulatory_input_hash": "regulatory-hash",
    }
    values[field] = ""

    with pytest.raises(ValueError, match="ENGINEERING_DEPENDENCY_INCOMPLETE"):
        require_canonical_engineering_chain(EngineeringDependency(**values))
