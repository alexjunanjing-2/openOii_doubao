from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1)
    story: str | None = None
    style: str | None = None
    status: str | None = None


class ProjectUpdate(BaseModel):
    title: str | None = None
    story: str | None = None
    style: str | None = None
    status: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    story: str | None
    style: str | None
    summary: str | None
    video_url: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectListRead(BaseModel):
    items: list[ProjectRead]
    total: int


class CharacterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    description: str | None
    image_url: str | None


class ShotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    order: int
    description: str
    prompt: str | None
    image_prompt: str | None
    image_url: str | None
    video_url: str | None
    duration: float | None


class ShotUpdate(BaseModel):
    order: int | None = Field(default=None, ge=1)
    description: str | None = None
    prompt: str | None = None
    image_prompt: str | None = None


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class RegenerateRequest(BaseModel):
    type: Literal["image", "video"]
    style_mode: Literal["cartoon", "realistic"] = "cartoon"


class GenerateRequest(BaseModel):
    seed: int | None = None
    notes: str | None = None
    auto_mode: bool = False
    style_mode: Literal["cartoon", "realistic"] = "cartoon"


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    status: str
    current_agent: str | None
    progress: float
    error: str | None
    resource_type: str | None  # 资源类型：character|shot|project
    resource_id: int | None    # 资源 ID
    style_mode: str  # cartoon|realistic
    created_at: datetime
    updated_at: datetime


class FeedbackRequest(BaseModel):
    content: str = Field(min_length=1)
    run_id: int | None = None
    style_mode: Literal["cartoon", "realistic"] = "cartoon"


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    run_id: int | None
    agent: str
    role: str
    content: str
    progress: float | None
    is_loading: bool
    style_mode: str  # cartoon|realistic
    created_at: datetime
