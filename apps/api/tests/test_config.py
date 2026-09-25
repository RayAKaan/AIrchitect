import pytest
from app.core.config import Settings, validate_production_settings


def test_local_mode_allows_development_secret() -> None:
    validate_production_settings(Settings(app_env="local", auth_secret="local-only-change-this-secret"))


@pytest.mark.parametrize("secret", ["", "local-only-change-this-secret", "replace-for-local-development", "short"])
def test_non_local_rejects_weak_or_default_secret(secret: str) -> None:
    with pytest.raises(ValueError, match="AUTH_SECRET"):
        validate_production_settings(Settings(app_env="production", auth_secret=secret))


def test_non_local_accepts_long_unique_secret() -> None:
    validate_production_settings(Settings(app_env="production", auth_secret="x" * 48))
