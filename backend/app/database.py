from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.models import Base

_engine = None
_session_factory = None


def get_session_factory():
    assert _session_factory is not None
    return _session_factory


def reset_engine() -> None:
    """Clear global engine (for tests / process isolation)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None


def _database_url(settings: Settings) -> str:
    if settings.database_url:
        return settings.database_url
    p = (settings.data_dir / "grantfiller.db").resolve()
    return f"sqlite+aiosqlite:///{p}"


def init_engine(settings: Settings):
    global _engine, _session_factory
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    url = _database_url(settings)
    if url.startswith("sqlite"):
        _engine = create_async_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    else:
        _engine = create_async_engine(url, echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


async def create_tables():
    assert _engine is not None
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    assert _session_factory is not None
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
