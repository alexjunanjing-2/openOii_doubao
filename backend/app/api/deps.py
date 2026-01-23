from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_session
from app.ws.manager import ConnectionManager, ws_manager


async def get_app_settings() -> Settings:
    return get_settings()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def get_ws_manager() -> ConnectionManager:
    return ws_manager


SettingsDep = Depends(get_app_settings)
SessionDep = Depends(get_db_session)
WsManagerDep = Depends(get_ws_manager)
