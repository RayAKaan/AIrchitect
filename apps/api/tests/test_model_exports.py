from app.domains.model import ArchitecturalModel, model_hash, validate_baseline_constraints


def test_public_model_contract_is_importable() -> None:
    assert ArchitecturalModel is not None
    assert callable(model_hash)
    assert callable(validate_baseline_constraints)
