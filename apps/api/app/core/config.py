from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Nazmak Building Feasibility Platform"
    app_env: str = "local"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://building:building@localhost:5432/building"
    decision_provider: str = "deterministic"
    auth_secret: str = "local-only-change-this-secret"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def validate_production_settings(config: Settings) -> None:
    """Fail closed on known development credentials outside local development."""
    if config.app_env.lower() == "local":
        return
    secret = config.auth_secret.strip()
    if secret in {"", "local-only-change-this-secret", "replace-for-local-development"} or len(secret) < 32:
        raise ValueError("AUTH_SECRET must be a unique secret of at least 32 characters outside local mode")
