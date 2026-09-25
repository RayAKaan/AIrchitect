from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

_engine = None
_session_factory = None

def get_engine():
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    get_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session

async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
