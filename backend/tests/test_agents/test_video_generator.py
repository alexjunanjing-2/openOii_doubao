from __future__ import annotations

import pytest
from sqlmodel import select

from app.agents.video_generator import VideoGeneratorAgent
from app.models.project import Shot
from tests.agent_fixtures import FakeLLM, FakeVideoService, make_context
from tests.factories import create_project, create_run, create_shot


@pytest.mark.asyncio
async def test_video_generator_creates_videos(test_session, test_settings):
    project = await create_project(test_session)
    run = await create_run(test_session, project_id=project.id)
    shot = await create_shot(test_session, project_id=project.id, video_url=None)

    video = FakeVideoService(url="http://video.test/shot.mp4")
    ctx = await make_context(
        test_session,
        test_settings,
        project=project,
        run=run,
        llm=FakeLLM("{}"),
        video=video,
    )

    agent = VideoGeneratorAgent()
    await agent.run(ctx)

    await test_session.refresh(shot)
    assert shot.video_url == "http://video.test/shot.mp4"
    assert shot.duration == 5.0

    res = await test_session.execute(select(Shot).where(Shot.project_id == project.id))
    assert len(res.scalars().all()) == 1
