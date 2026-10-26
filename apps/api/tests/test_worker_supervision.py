from datetime import UTC, datetime, timedelta

import pytest

from app.domains.lifecycle.worker_supervision import WorkerHeartbeat, worker_is_live


def test_worker_is_live_within_timeout() -> None:
    now = datetime(2026, 10, 27, 1, 0, tzinfo=UTC)
    heartbeat = WorkerHeartbeat("worker-1", now - timedelta(seconds=30), 1, 4, 0)
    assert worker_is_live(heartbeat, now=now)


def test_worker_is_not_live_after_timeout() -> None:
    now = datetime(2026, 10, 27, 1, 0, tzinfo=UTC)
    heartbeat = WorkerHeartbeat("worker-1", now - timedelta(minutes=3), 0, 4, 0)
    assert not worker_is_live(heartbeat, now=now)


def test_worker_rejects_invalid_counters() -> None:
    heartbeat = WorkerHeartbeat("worker-1", datetime.now(UTC), -1, 0, 0)
    with pytest.raises(ValueError, match="counters"):
        heartbeat.validate()
