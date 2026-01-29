from __future__ import annotations

import json

import pytest

from app.agents.review import ReviewAgent
from tests.agent_fixtures import FakeLLM, make_context
from tests.factories import create_agent_message, create_project, create_run


@pytest.mark.asyncio
async def test_review_agent_no_feedback_defaults(test_session, test_settings):
    ctx = await make_context(test_session, test_settings, llm=FakeLLM("{}"))

    agent = ReviewAgent()
    result = await agent.run(ctx)
    assert result["start_agent"] == "scriptwriter"


@pytest.mark.asyncio
async def test_review_agent_routing_with_targets(test_session, test_settings):
    project = await create_project(test_session)
    run = await create_run(test_session, project_id=project.id)
    await create_agent_message(test_session, run_id=run.id, content="More detail")

    payload = {
        "analysis": {"feedback_type": "character", "summary": "Adjust character"},
        "routing": {"start_agent": "character_artist", "mode": "incremental", "reason": "Fix"},
        "target_ids": {"character_ids": [1], "shot_ids": [2]},
    }
    llm = FakeLLM(json.dumps(payload))
    ctx = await make_context(test_session, test_settings, project=project, run=run, llm=llm)

    agent = ReviewAgent()
    result = await agent.run(ctx)
    assert result["start_agent"] == "character_artist"
    assert result["mode"] == "incremental"
    assert result["target_ids"].character_ids == [1]
    assert result["target_ids"].shot_ids == [2]
