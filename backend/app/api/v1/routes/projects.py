from __future__ import annotations

from datetime import datetime, UTC

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.models.agent_run import AgentMessage, AgentRun
from app.models.message import Message
from app.models.project import Character, Project, Scene, Shot
from app.schemas.project import (
    CharacterRead,
    MessageRead,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    SceneRead,
    ShotRead,
)
from app.services.file_cleaner import delete_file, delete_files

router = APIRouter()


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, session: AsyncSession = SessionDep):
    project = Project(
        title=payload.title,
        story=payload.story,
        style=payload.style,
        status=payload.status or "draft",
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
async def list_projects(session: AsyncSession = SessionDep):
    res = await session.execute(select(Project).order_by(Project.created_at.desc()))
    items = res.scalars().all()
    return [ProjectRead.model_validate(p) for p in items]


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: int, session: AsyncSession = SessionDep):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(project_id: int, payload: ProjectUpdate, session: AsyncSession = SessionDep):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(project, k, v)
    project.updated_at = utcnow()
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, session: AsyncSession = SessionDep):
    """完全删除项目及所有关联数据（包括文件）"""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 0. 先取消所有运行中的任务（防止异步任务继续操作）
    await session.execute(
        AgentRun.__table__.update()
        .where(AgentRun.project_id == project_id)
        .where(AgentRun.status.in_(["queued", "running"]))
        .values(status="cancelled")
    )

    # 1. 收集并删除所有关联文件
    # 1.1 删除项目最终视频
    delete_file(project.video_url)

    # 1.2 删除角色图片
    chars_res = await session.execute(
        select(Character).where(Character.project_id == project_id)
    )
    chars = chars_res.scalars().all()
    delete_files([c.image_url for c in chars])

    # 1.3 删除分镜图片和视频
    scene_ids_subq = select(Scene.id).where(Scene.project_id == project_id)
    shots_res = await session.execute(
        select(Shot).where(Shot.scene_id.in_(scene_ids_subq))
    )
    shots = shots_res.scalars().all()
    delete_files([s.image_url for s in shots])
    delete_files([s.video_url for s in shots])

    # 2. 删除 Message（聊天消息）
    await session.execute(delete(Message).where(Message.project_id == project_id))

    # 3. 删除 AgentMessage（通过 AgentRun 关联）
    run_ids_subq = select(AgentRun.id).where(AgentRun.project_id == project_id)
    await session.execute(delete(AgentMessage).where(AgentMessage.run_id.in_(run_ids_subq)))

    # 4. 删除 AgentRun
    await session.execute(delete(AgentRun).where(AgentRun.project_id == project_id))

    # 5. 删除 Shot（通过 Scene 关联）
    await session.execute(delete(Shot).where(Shot.scene_id.in_(scene_ids_subq)))

    # 6. 删除 Scene
    await session.execute(delete(Scene).where(Scene.project_id == project_id))

    # 7. 删除 Character
    await session.execute(delete(Character).where(Character.project_id == project_id))

    # 8. 最后删除 Project
    await session.delete(project)
    await session.commit()
    return None


@router.get("/{project_id}/characters", response_model=list[CharacterRead])
async def list_characters(project_id: int, session: AsyncSession = SessionDep):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    res = await session.execute(select(Character).where(Character.project_id == project_id))
    return [CharacterRead.model_validate(c) for c in res.scalars().all()]


@router.get("/{project_id}/scenes", response_model=list[SceneRead])
async def list_scenes(project_id: int, session: AsyncSession = SessionDep):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    res = await session.execute(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.order.asc())
    )
    return [SceneRead.model_validate(s) for s in res.scalars().all()]


@router.get("/{project_id}/shots", response_model=list[ShotRead])
async def list_shots(project_id: int, session: AsyncSession = SessionDep):
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    res = await session.execute(
        select(Shot)
        .join(Scene, Shot.scene_id == Scene.id)
        .where(Scene.project_id == project_id)
        .order_by(Scene.order.asc(), Shot.order.asc())
    )
    return [ShotRead.model_validate(s) for s in res.scalars().all()]


@router.get("/{project_id}/messages", response_model=list[MessageRead])
async def list_messages(project_id: int, session: AsyncSession = SessionDep):
    """获取项目的所有消息记录"""
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    res = await session.execute(
        select(Message)
        .where(Message.project_id == project_id)
        .order_by(Message.created_at.asc())
    )
    return [MessageRead.model_validate(m) for m in res.scalars().all()]

