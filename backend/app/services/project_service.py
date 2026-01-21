from __future__ import annotations

from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project: Project) -> Project:
        project.created_at = utcnow()
        project.updated_at = utcnow()
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get(self, project_id: int) -> Project | None:
        return await self.session.get(Project, project_id)

    async def list(self) -> list[Project]:
        res = await self.session.execute(select(Project).order_by(Project.created_at.desc()))
        return res.scalars().all()

    async def update(self, project: Project, **fields) -> Project:
        for k, v in fields.items():
            setattr(project, k, v)
        project.updated_at = utcnow()
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)
        await self.session.commit()

