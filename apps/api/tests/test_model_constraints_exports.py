from app.domains.model import ModelConstraintViolation


def test_constraint_violation_is_public() -> None:
    violation = ModelConstraintViolation(code="example", message="example")
    assert violation.element_id is None
