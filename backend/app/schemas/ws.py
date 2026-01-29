from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


WsEventType = Literal[
    "connected",
    "pong",
    "echo",
    "run_started",
    "run_progress",
    "run_message",
    "run_completed",
    "run_failed",
    "run_awaiting_confirm",  # 等待用户确认
    "run_confirmed",         # 用户已确认
    "run_cancelled",         # 任务已取消
    "agent_handoff",         # Agent 交接
    "character_created",     # 角色创建
    "character_updated",     # 角色更新（图片生成等）
    "character_deleted",     # 角色删除
    "shot_created",          # 分镜创建
    "shot_updated",          # 分镜更新（图片/视频生成等）
    "shot_deleted",          # 分镜删除
    "project_updated",       # 项目更新（视频拼接完成等）
    "data_cleared",          # 数据清理（重新生成时）
]


class WsEvent(BaseModel):
    type: WsEventType
    data: dict[str, Any] = {}

