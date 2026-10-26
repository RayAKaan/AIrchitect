from __future__ import annotations

import asyncio
import logging
import os
import socket
from collections.abc import Awaitable, Callable
from datetime import timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.session import get_engine
from app.domains.commands.regeneration_worker import RegenerationWorker

logger = logging.getLogger("airchitect.regeneration_worker")


async def run_regeneration_worker(
    *,
    worker_id: str | None = None,
    poll_interval: float = 1.0,
    lease_timeout: timedelta = timedelta(minutes=5),
    stop: Callable[[], Awaitable[bool]] | None = None,
) -> None:
    if poll_interval <= 0:
        raise ValueError("poll_interval must be positive")
    if lease_timeout <= timedelta(0):
        raise ValueError("lease_timeout must be positive")
    identity = worker_id or f"{socket.gethostname()}:{os.getpid()}"
    if not identity.strip():
        raise ValueError("worker_id must not be empty")

    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    worker = RegenerationWorker(worker_id=identity)
    while True:
        if stop is not None and await stop():
            return
        async with factory() as session:
            try:
                await worker.queue.recover_expired_leases(session, lease_timeout=lease_timeout)
                await session.commit()
                result = await worker.run_once(session)
                if result.status == "FAILED":
                    logger.warning("regeneration task failed", extra={"job_id": result.job_id, "error_code": result.error_code})
            except asyncio.CancelledError:
                await session.rollback()
                raise
            except Exception:
                await session.rollback()
                logger.exception("regeneration worker iteration failed")
        if stop is not None and await stop():
            return
        await asyncio.sleep(poll_interval)
