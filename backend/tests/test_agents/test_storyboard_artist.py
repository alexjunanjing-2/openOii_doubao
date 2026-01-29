from __future__ import annotations

import pytest
from sqlmodel import select

from app.agents.storyboard_artist import StoryboardArtistAgent
from app.models.project import Shot
from tests.agent_fixtures import FakeImageService, FakeLLM, make_context
from tests.factories import create_project, create_run, create_shot


@pytest.mark.asyncio
async def test_storyboard_artist_generates_shot_images(test_session, test_settings):
    project = await create_project(test_session)
    run = await create_run(test_session, project_id=project.id)
    shot = await create_shot(test_session, project_id=project.id, image_url=None)

    image = FakeImageService(url="http://image.test/shot.png")
    ctx = await make_context(
        test_session,
        test_settings,
        project=project,
        run=run,
        llm=FakeLLM("{}"),
        image=image,
    )

    agent = StoryboardArtistAgent()
    await agent.run(ctx)

    await test_session.refresh(shot)
    assert shot.image_url == "http://image.test/shot.png"
    assert any(event[1]["type"] == "shot_updated" for event in ctx.ws.events)

    res = await test_session.execute(select(Shot).where(Shot.project_id == project.id))
    assert len(res.scalars().all()) == 1
