import pytest
from app.core.config import Settings, validate_production_settings


def test_local_mode_allows_development_secret() -> None:
    validate_production_settings(Settings(app_env="local", auth_secret="local-only-change-this-secret"))


@pytest.mark.parametrize("secret", ["", "local-only-change-this-secret", "replace-for-local-development", "short"])
def test_non_local_rejects_weak_or_default_secret(secret: str) -> None:
    with pytest.raises(ValueError, match="AUTH_SECRET"):
        validate_production_settings(Settings(app_env="production", auth_secret=secret))


def production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "auth_secret": "x" * 48,
        "database_url": "postgresql+asyncpg://prod_user:strong-password@db.example.com/building",
        "cad_allow_legacy_engine": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_non_local_accepts_valid_production_configuration() -> None:
    validate_production_settings(production_settings())


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite+aiosqlite:///./app.db",
        "postgresql+asyncpg://building:building@db:5432/building",
        "postgresql+asyncpg://prod_user:strong-password@localhost/building",
    ],
)
def test_production_rejects_unsafe_database_configuration(database_url: str) -> None:
    with pytest.raises(ValueError, match="DATABASE_URL"):
        validate_production_settings(production_settings(database_url=database_url))


def test_production_rejects_legacy_geometry() -> None:
    with pytest.raises(ValueError, match="GEOMETRY_ENGINE"):
        validate_production_settings(production_settings(geometry_engine="legacy"))


def test_production_rejects_legacy_fallback() -> None:
    with pytest.raises(ValueError, match="CAD_ALLOW_LEGACY_ENGINE"):
        validate_production_settings(production_settings(cad_allow_legacy_engine=True))


def test_test_environment_can_use_isolated_test_database() -> None:
    validate_production_settings(Settings(app_env="test", database_url="sqlite+aiosqlite:///./test.db"))
