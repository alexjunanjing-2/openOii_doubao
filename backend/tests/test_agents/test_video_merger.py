from __future__ import annotations

import pytest
from sqlmodel import select

from app.agents.video_merger import VideoMergerAgent
from app.models.project import Project
from tests.agent_fixtures import FakeLLM, FakeVideoService, make_context
from tests.factories import create_project, create_run, create_shot


@pytest.mark.asyncio
async def test_video_merger_sets_project_video(test_session, test_settings):
    project = await create_project(test_session)
    run = await create_run(test_session, project_id=project.id)
    await create_shot(test_session, project_id=project.id, video_url="http://video.test/1.mp4")

    video = FakeVideoService(merged_url="/static/videos/merged.mp4")
    ctx = await make_context(
        test_session,
        test_settings,
        project=project,
        run=run,
        llm=FakeLLM("{}"),
        video=video,
    )

    agent = VideoMergerAgent()
    await agent.run(ctx)

    await test_session.refresh(project)
    assert project.video_url == "/static/videos/merged.mp4"

    res = await test_session.execute(select(Project).where(Project.id == project.id))
    assert res.scalar_one_or_none() is not None
