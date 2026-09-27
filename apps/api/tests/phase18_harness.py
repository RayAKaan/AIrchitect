"""The API and CAD-harness fixtures shared by the Phase 18 test modules.

These live here rather than in one of the test modules because pytest only
auto-discovers fixtures from a conftest, and importing a fixture into a test module
instead shadows the fixture name with the test parameter of the same name, which
ruff reports as F811. :mod:`tests.conftest` re-exports what is defined here.

The design is the same as the S10 tests it replaces: the real router runs against
the real ASGI app, with a real subprocess standing in for the CAD worker. Nothing
native is imported and nothing in the API's own code is mocked out -- the
orchestrator, the persistence, the store, the routes and the engineering
calculation all run for real. Only the geometry kernel is faked.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.session import get_session
from app.domains.cad.config import CadConfig
from app.db.models import Base
from app.main import app
from tests.phase18_fake_worker import SCENARIO_ENV, FakeWorker, fake_worker

__all__ = ["CadHarness", "api", "cad", "db"]


@pytest.fixture
async def api():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Exposed so a test can put a row into a state the public API cannot reach --
        # a recorded hash that no longer matches the world it was computed from, or a
        # run whose validation was never established.
        client.session_factory = factory  # type: ignore[attr-defined]
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
def db(api: httpx.AsyncClient):
    """A session on the same in-memory database the API is using."""

    @asynccontextmanager
    async def session():
        async with api.session_factory() as open_session:  # type: ignore[attr-defined]
            yield open_session

    return session


class CadHarness:
    """Installs a fake-worker-backed :class:`CadConfig` as the router's config.

    The router reads its configuration through ``CadConfig.from_settings()`` rather
    than taking it as a parameter, which is what makes it testable at all: a test can
    hand the route a configuration that points at a throwaway package tree and a
    throwaway artifact root, and every other line of the request path stays real.
    """

    def __init__(self, worker: FakeWorker, artifact_root: Path, monkeypatch: pytest.MonkeyPatch):
        self.worker = worker
        self.artifact_root = artifact_root
        self.config = worker.config(artifact_root)
        self._monkeypatch = monkeypatch
        self._install()

    def _install(self) -> None:
        config = self.config

        def from_settings(cls: type, settings: Any = None) -> CadConfig:
            return config

        self._monkeypatch.setattr(CadConfig, "from_settings", classmethod(from_settings))

    def set(self, **overrides: Any) -> CadConfig:
        """Rebuild the installed config with *overrides* applied."""
        self.config = self.worker.config(self.artifact_root, **overrides)
        self._install()
        return self.config

    def worker_with(self, scenario: str) -> FakeWorker:
        """Switch the fake worker to a different behaviour for the next job."""
        self._monkeypatch.setenv(SCENARIO_ENV, scenario)
        return self.worker


@pytest.fixture
def cad(fake_worker: FakeWorker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CadHarness:  # noqa: F811 - consumes the imported fixture; pytest resolves it by parameter name
    return CadHarness(fake_worker, tmp_path / "artifacts", monkeypatch)
