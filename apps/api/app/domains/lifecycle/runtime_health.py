from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class RuntimeHealth:
    database: str
    checked_at: datetime

    @property
    def ready(self) -> bool:
        return self.database == "ok"

    def as_dict(self) -> dict[str, object]:
        return {"ready": self.ready, "database": self.database, "checked_at": self.checked_at.isoformat()}


async def check_runtime_health(session: AsyncSession) -> RuntimeHealth:
    try:
        await session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unavailable"
    return RuntimeHealth(database=database, checked_at=datetime.now(timezone.utc))
