"""数据库连接管理（精简版）"""
import logging
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_engine = None
_async_session_maker = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.SQL_ECHO,
            pool_pre_ping=True,
        )
    return _engine


def _get_session_maker():
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            _get_engine(), class_=AsyncSession, expire_on_commit=False,
        )
    return _async_session_maker


class _EngineProxy:
    def __getattr__(self, name):
        return getattr(_get_engine(), name)
    def begin(self):
        return _get_engine().begin()
    async def dispose(self):
        return await _get_engine().dispose()


class _SessionMakerProxy:
    def __call__(self, *args, **kwargs):
        return _get_session_maker()(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(_get_session_maker(), name)


engine = _EngineProxy()
async_session_maker = _SessionMakerProxy()


class Base(DeclarativeBase):
    pass


async def create_tables() -> None:
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_database_ready() -> None:
    if settings.DB_AUTO_CREATE_SCHEMA:
        await create_tables()
    else:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))


async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
