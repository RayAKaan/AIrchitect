from app.domains.model.version import MODEL_SCHEMA_VERSION


def test_model_schema_version_is_explicit() -> None:
    assert MODEL_SCHEMA_VERSION == "1"
