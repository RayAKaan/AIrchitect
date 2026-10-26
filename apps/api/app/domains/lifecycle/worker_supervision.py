from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class WorkerHeartbeat:
    worker_id: str
    observed_at: datetime
    active_jobs: int
    completed_jobs: int
    failed_jobs: int

    def validate(self) -> None:
        if not self.worker_id.strip():
            raise ValueError("worker_id must not be empty")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if min(self.active_jobs, self.completed_jobs, self.failed_jobs) < 0:
            raise ValueError("worker counters must not be negative")


def worker_is_live(
    heartbeat: WorkerHeartbeat,
    *,
    now: datetime,
    timeout: timedelta = timedelta(minutes=2),
) -> bool:
    heartbeat.validate()
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if timeout <= timedelta(0):
        raise ValueError("timeout must be positive")
    age = now.astimezone(UTC) - heartbeat.observed_at.astimezone(UTC)
    return timedelta(0) <= age <= timeout
