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

    # --- Phase 5 CAD/BIM toolchain -------------------------------------------------
    # "cad_bim" is the real OpenCASCADE/FreeCAD/IfcOpenShell pipeline. "legacy" is the
    # pre-Phase-5 scratch cuboid generator, retained only as a migration aid and
    # scheduled for deletion once parity and acceptance gates pass.
    geometry_engine: str = "cad_bim"
    # Interpreter for the isolated worker virtualenv. Empty means auto-discover from
    # CAD_WORKER_VENV_ROOT; the API interpreter is never used for CAD work.
    cad_worker_python: str = ""
    cad_worker_venv_root: str = "H:/.cad-tools/worker-venv"
    cad_freecad_root: str = "H:/.cad-tools/freecad-1.1.3/FreeCAD_1.1.3-Windows-x86_64-py311"
    # Where generated binaries (FCStd/STEP/IFC/GLB) are written before upload.
    cad_artifact_root: str = "H:/.cad-tools/artifacts"
    # "freecad" drives FreeCADCmd for native documents; "occt" uses the standalone
    # OCP kernel only. "auto" prefers freecad and falls back to occt.
    cad_provider: str = "auto"
    cad_ifc_schema: str = "IFC4"
    cad_job_timeout_seconds: float = 180.0
    cad_freecad_timeout_seconds: float = 180.0
    cad_worker_memory_limit_mb: int = 4096
    cad_max_output_bytes: int = 67108864
    cad_max_request_bytes: int = 1048576
    cad_mesh_deflection_m: float = 0.05
    cad_mesh_angular_deflection_rad: float = 0.35
    cad_volume_tolerance_ratio: float = 0.005
    cad_area_tolerance_ratio: float = 0.005
    cad_linear_tolerance_m: float = 0.01
    cad_write_fcstd: bool = True
    cad_write_step: bool = True
    cad_write_ifc: bool = True
    cad_write_glb: bool = True
    cad_allow_legacy_engine: bool = True

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
