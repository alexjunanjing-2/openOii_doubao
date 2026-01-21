from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.schemas.ws import WsEvent


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, project_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._conns[project_id].add(websocket)

    async def disconnect(self, project_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            if project_id in self._conns:
                self._conns[project_id].discard(websocket)
                if not self._conns[project_id]:
                    self._conns.pop(project_id, None)

    async def send_event(self, project_id: int, event: dict[str, Any] | WsEvent) -> None:
        if isinstance(event, dict):
            event = WsEvent.model_validate(event)
        payload = event.model_dump()
        conns = list(self._conns.get(project_id, set()))
        for ws in conns:
            if ws.client_state != WebSocketState.CONNECTED:
                continue
            try:
                await ws.send_json(payload)
            except Exception:
                await self.disconnect(project_id, ws)


ws_manager = ConnectionManager()

