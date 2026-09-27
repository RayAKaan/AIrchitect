"""Checks that the Phase 18 migration and the SQLAlchemy models cannot drift.

The API's test suite builds its schema with ``Base.metadata.create_all`` against
SQLite, so the models are what the tests exercise. Alembic is what a real
deployment runs. Nothing in the suite connects to PostgreSQL, which means a
column added to a model and forgotten in the migration would pass every test and
then fail on first deploy.

This module therefore runs the whole migration chain against a temporary SQLite
database and compares the result to the models: every table, every column, and
every type. It is the check that makes it safe to trust either side alone.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import settings
from app.db.models import Base

API_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    return cfg


@pytest.fixture(scope="module")
def migrated_db() -> str:
    """Run every migration in order against a throwaway SQLite file.

    ``alembic/env.py`` overwrites the configured URL with ``settings.database_url``,
    so the only way to redirect it is to set that setting. An aiosqlite URL is
    required because env.py builds its engine with ``async_engine_from_config``.
    """
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "migrated.db"
        previous = settings.database_url
        settings.database_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
        try:
            command.upgrade(_alembic_config(), "head")
        finally:
            settings.database_url = previous
        yield str(db_path)


def _model_tables() -> dict[str, dict[str, str]]:
    return {
        name: {col.name: str(col.type) for col in table.columns}
        for name, table in Base.metadata.tables.items()
    }


def _migrated_tables(db_path: str) -> dict[str, dict[str, str]]:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        inspector = inspect(engine)
        return {
            name: {col["name"]: str(col["type"]) for col in inspector.get_columns(name)}
            for name in inspector.get_table_names()
            if name != "alembic_version"
        }
    finally:
        engine.dispose()


def test_migration_chain_runs_to_head(migrated_db: str) -> None:
    tables = _migrated_tables(migrated_db)
    assert "cad_job_runs" in tables
    assert "cad_artifacts" in tables


def test_migration_and_models_agree_on_table_names(migrated_db: str) -> None:
    assert sorted(_migrated_tables(migrated_db)) == sorted(_model_tables())


def test_migration_and_models_agree_on_cad_columns(migrated_db: str) -> None:
    """The Phase 18 tables specifically, column by column."""
    migrated = _migrated_tables(migrated_db)
    models = _model_tables()
    for table in ("cad_job_runs", "cad_artifacts"):
        assert sorted(migrated[table]) == sorted(models[table]), (
            f"{table} differs between the migration and the model; "
            f"only in migration: {sorted(set(migrated[table]) - set(models[table]))}; "
            f"only in model: {sorted(set(models[table]) - set(migrated[table]))}"
        )


def test_migration_and_models_agree_on_cad_column_types(migrated_db: str) -> None:
    migrated = _migrated_tables(migrated_db)
    models = _model_tables()
    mismatched: list[str] = []
    for table in ("cad_job_runs", "cad_artifacts"):
        for column, model_type in models[table].items():
            if migrated[table][column] != model_type:
                mismatched.append(
                    f"{table}.{column}: migration={migrated[table][column]} model={model_type}"
                )
    assert not mismatched, "column type drift:\n  " + "\n  ".join(mismatched)


def test_byte_size_is_not_a_32_bit_integer(migrated_db: str) -> None:
    """byte_size must be BigInteger; Integer would overflow past 2 GiB."""
    migrated = _migrated_tables(migrated_db)
    assert "BIGINT" in migrated["cad_artifacts"]["byte_size"].upper()


def test_no_geometry_binary_is_stored_in_a_json_column(migrated_db: str) -> None:
    """Guard the boundary: base64 payloads must never land in the database.

    The runner hands artifacts back base64-encoded; if a future refactor persisted
    the encoded payload into one of the JSON columns, a multi-megabyte STEP file
    would be duplicated into every row that referenced the run. The blob lives on
    disk and is addressed by storage_key.
    """
    migrated = _migrated_tables(migrated_db)
    blob_shaped = [c for c in migrated["cad_artifacts"] if c in {"payload", "payload_json", "data", "content"}]
    assert not blob_shaped, f"cad_artifacts must not carry inline binary columns: {blob_shaped}"
