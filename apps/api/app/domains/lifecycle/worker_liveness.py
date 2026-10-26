from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class WorkerLiveness:
    worker_id: str
    checked_at: datetime

    @classmethod
    def for_worker(cls, worker_id: str) -> WorkerLiveness:
        normalized = worker_id.strip()
        if not normalized:
            raise ValueError("worker_id must not be empty")
        return cls(worker_id=normalized, checked_at=datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, str]:
        return {"worker_id": self.worker_id, "checked_at": self.checked_at.isoformat()}
