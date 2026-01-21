from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, WsManagerDep
from app.models.project import Project, Scene, Shot
from app.schemas.project import SceneRead, SceneUpdate
from app.services.file_cleaner import delete_file, delete_files
from app.ws.manager import ConnectionManager

router = APIRouter()


def _scene_payload(scene: Scene) -> dict[str, Any]:
    return {
        "id": scene.id,
        "project_id": scene.project_id,
        "order": scene.order,
        "description": scene.description,
    }


@router.put("/{scene_id}", response_model=SceneRead)
async def update_scene(
    scene_id: int,
    payload: SceneUpdate,
    session: AsyncSession = SessionDep,
    ws: ConnectionManager = WsManagerDep,
):
    scene = await session.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(scene, k, v)

    session.add(scene)
    await session.commit()
    await session.refresh(scene)

    await ws.send_event(
        scene.project_id,
        {"type": "scene_updated", "data": {"scene": _scene_payload(scene)}},
    )
    return SceneRead.model_validate(scene)


@router.delete("/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scene(
    scene_id: int,
    session: AsyncSession = SessionDep,
    ws: ConnectionManager = WsManagerDep,
):
    scene = await session.get(Scene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    project_id = scene.project_id

    res = await session.execute(select(Shot).where(Shot.scene_id == scene_id))
    shots = list(res.scalars().all())
    shot_ids = [s.id for s in shots if s.id is not None]

    delete_files([s.image_url for s in shots])
    delete_files([s.video_url for s in shots])

    for shot in shots:
        await session.delete(shot)

    project = await session.get(Project, project_id)
    cleared_project_video = False
    if project and project.video_url:
        delete_file(project.video_url)
        project.video_url = None
        session.add(project)
        cleared_project_video = True

    await session.delete(scene)
    await session.commit()

    for shot_id in shot_ids:
        await ws.send_event(project_id, {"type": "shot_deleted", "data": {"shot_id": shot_id}})
    await ws.send_event(project_id, {"type": "scene_deleted", "data": {"scene_id": scene_id}})
    if cleared_project_video:
        await ws.send_event(
            project_id,
            {"type": "project_updated", "data": {"project": {"id": project_id, "video_url": None}}},
        )

    return None
