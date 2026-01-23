from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.api.deps import get_app_settings, get_db_session, get_ws_manager
from app.config import Settings
from app.main import create_app
from app.models import agent_run, message, project  # noqa: F401


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        anthropic_api_key="test-key",
        image_api_key="test-key",
        video_api_key="test-key",
    )


class StubWsManager:
    def __init__(self) -> None:
        self.events: list[tuple[int, dict]] = []

    async def send_event(self, project_id: int, event: dict) -> None:
        self.events.append((project_id, event))


@pytest_asyncio.fixture(scope="function")
async def test_session(test_settings: Settings) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(test_settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture()
def ws_manager() -> StubWsManager:
    return StubWsManager()


@pytest_asyncio.fixture(scope="function")
async def app(test_session: AsyncSession, test_settings: Settings, ws_manager: StubWsManager):
    app = create_app()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    async def override_get_settings() -> Settings:
        return test_settings

    async def override_get_ws() -> StubWsManager:
        return ws_manager

    app.dependency_overrides[get_db_session] = override_get_session
    app.dependency_overrides[get_app_settings] = override_get_settings
    app.dependency_overrides[get_ws_manager] = override_get_ws
    return app


@pytest_asyncio.fixture(scope="function")
async def async_client(app):
    transport = ASGITransport(app=app)

    class _AsyncClientWithYield(AsyncClient):
        async def request(self, *args, **kwargs):
            loop = asyncio.get_running_loop()
            task = loop.create_task(super().request(*args, **kwargs))
            # ASGITransport + body-carrying requests can deadlock on this runtime
            # unless the request coroutine gets at least one scheduling slice.
            await asyncio.sleep(0.01)
            return await task

    async with _AsyncClientWithYield(transport=transport, base_url="http://test") as client:
        yield client


@asynccontextmanager
async def _no_lifespan(_: object):
    yield


@pytest.fixture()
def ws_client(app):
    app.router.lifespan_context = _no_lifespan
    return TestClient(app)
