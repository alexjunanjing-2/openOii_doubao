from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.config import get_settings
from app.models import agent_run, message, project  # noqa: F401


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=settings.db_echo, pool_pre_ping=True)


engine: AsyncEngine = _build_engine()
async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """Initialize database tables and cleanup stale runs."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # 清理服务重启前遗留的 running/queued 状态的 run（它们已经不会继续执行了）
    async with async_session_maker() as session:
        from app.models.agent_run import AgentRun

        await session.execute(
            update(AgentRun)
            .where(AgentRun.status.in_(["queued", "running"]))
            .values(status="cancelled", error="Service restarted")
        )
        await session.commit()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
