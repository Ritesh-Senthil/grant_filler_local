from collections.abc import AsyncGenerator

from sqlalchemy import text
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


def _migrate_sqlite_schema(sync_conn) -> None:
    """Add columns introduced after first deploy (SQLite has no ALTER IF NOT EXISTS)."""
    r = sync_conn.execute(text("PRAGMA table_info(grants)"))
    gcols = {row[1] for row in r.fetchall()}
    if "source_chunks_json" not in gcols:
        sync_conn.execute(text("ALTER TABLE grants ADD COLUMN source_chunks_json TEXT"))

    r = sync_conn.execute(text("PRAGMA table_info(facts)"))
    fcols = {row[1] for row in r.fetchall()}
    if "learned_from_grant_id" not in fcols:
        sync_conn.execute(text("ALTER TABLE facts ADD COLUMN learned_from_grant_id VARCHAR(64)"))
    if "learned_from_question_id" not in fcols:
        sync_conn.execute(text("ALTER TABLE facts ADD COLUMN learned_from_question_id VARCHAR(128)"))

    r = sync_conn.execute(text("PRAGMA table_info(organizations)"))
    ocols = {row[1] for row in r.fetchall()}
    if "header_display_name" not in ocols:
        sync_conn.execute(text("ALTER TABLE organizations ADD COLUMN header_display_name VARCHAR(512) DEFAULT ''"))
    if "banner_file_key" not in ocols:
        sync_conn.execute(text("ALTER TABLE organizations ADD COLUMN banner_file_key VARCHAR(512)"))

    r = sync_conn.execute(text("PRAGMA table_info(answers)"))
    acols = {row[1] for row in r.fetchall()}
    if "evidence_fact_ids" not in acols:
        sync_conn.execute(text("ALTER TABLE answers ADD COLUMN evidence_fact_ids TEXT"))


async def create_tables():
    assert _engine is not None
    url = str(_engine.url)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in url:
            await conn.run_sync(_migrate_sqlite_schema)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    assert _session_factory is not None
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
