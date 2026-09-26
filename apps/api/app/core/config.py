from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Building Feasibility Platform"
    app_env: str = "local"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://building:building@localhost:5432/building"
    decision_provider: str = "deterministic"
    llm_provider: str = "deterministic"
    llm_model: str = "deterministic-local"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = 30.0
    llm_max_input_tokens: int = 12000
    llm_max_output_tokens: int = 1200
    llm_input_cost_per_million_usd: float = 0.0
    llm_output_cost_per_million_usd: float = 0.0
    jev_enabled: bool = False
    jev_api_key: str = ""
    jev_model: str = "jev-latest"
    jev_base_url: str = "https://api.typesafe.ai"
    jev_timeout_seconds: float = 15.0
    jev_max_input_tokens: int = 12000
    jev_input_cost_per_million_usd: float = 0.042
    assistant_rate_limit_per_minute: int = 20
    auth_secret: str = "local-only-change-this-secret"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def get_settings() -> Settings:
    return settings


def validate_production_settings(config: Settings) -> None:
    """Fail closed on known development credentials outside local development."""
    if config.app_env.lower() == "local":
        return
    secret = config.auth_secret.strip()
    if secret in {"", "local-only-change-this-secret", "replace-for-local-development"} or len(secret) < 32:
        raise ValueError("AUTH_SECRET must be a unique secret of at least 32 characters outside local mode")
