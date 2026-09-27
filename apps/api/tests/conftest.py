"""Shared pytest fixtures.

The CAD runner fixtures live in :mod:`tests.phase18_fake_worker` rather than here
so the stand-in worker itself stays readable as one piece. The API and CAD-harness
fixtures live in :mod:`tests.phase18_harness`. All of them are re-exported into the
conftest because pytest only auto-discovers fixtures from a conftest, and importing
them into a test module instead would shadow the fixture names with the test
parameters and trip ruff's F811.
"""

from tests.phase18_fake_worker import fake_worker, worker_with
from tests.phase18_harness import api, cad, db

__all__ = ["api", "cad", "db", "fake_worker", "worker_with"]
