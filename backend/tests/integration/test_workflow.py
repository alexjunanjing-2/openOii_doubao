from __future__ import annotations

import json

import pytest
from sqlmodel import select

import app.agents.orchestrator as orchestrator_mod
from app.agents.orchestrator import GenerationOrchestrator
from app.models.agent_run import AgentRun
from app.models.project import Character, Project, Scene, Shot
from app.schemas.project import GenerateRequest
from app.services.llm import LLMResponse
from tests.agent_fixtures import DummyWsManager
from tests.factories import create_project, create_run


class StubLLM:
    responses: list[str] = []

    def __init__(self, settings):
        self.settings = settings

    async def stream(self, **kwargs):
        if not self.responses:
            raise RuntimeError("No stub response configured")
        text = self.responses.pop(0)
        yield {"type": "final", "response": LLMResponse(text=text, tool_calls=[], raw=None)}


class StubImage:
    def __init__(self, settings):
        self.settings = settings
        self.count = 0

    async def generate_url(self, **kwargs):
        self.count += 1
        return f"http://image.test/{self.count}"

    async def cache_external_image(self, url: str) -> str:
        return url


class StubVideo:
    def __init__(self, settings):
        self.settings = settings
        self.count = 0

    async def generate_url(self, **kwargs):
        self.count += 1
        return f"http://video.test/{self.count}"

    async def merge_urls(self, video_urls):
        return "/static/videos/merged.mp4"


@pytest.mark.asyncio
async def test_full_workflow(monkeypatch, test_session, test_settings):
    project = await create_project(test_session, title="Workflow")
    run = await create_run(test_session, project_id=project.id, status="queued")
    ws = DummyWsManager()

    StubLLM.responses = [
        json.dumps(
            {
                "story_breakdown": {"logline": "Test"},
                "key_elements": {"characters": ["Hero"]},
                "style_recommendation": {"primary": "anime"},
                "project_update": {"title": "Workflow", "style": "anime"},
            }
        ),
        json.dumps(
            {
                "project_update": {"style": "anime", "status": "planning"},
                "director_notes": {"vision": "Focus"},
                "scene_outline": [{"title": "Scene 1"}],
            }
        ),
        json.dumps(
            {
                "project_update": {"status": "scripted"},
                "characters": [{"name": "Hero", "description": "Brave"}],
                "scenes": [
                    {
                        "order": 1,
                        "description": "Scene 1",
                        "shot_plan": [{"description": "Shot 1", "prompt": "Action"}],
                    }
                ],
            }
        ),
    ]

    async def _noop_clear(_: int) -> None:
        return None

    monkeypatch.setattr(orchestrator_mod, "LLMService", StubLLM)
    monkeypatch.setattr(orchestrator_mod, "ImageService", StubImage)
    monkeypatch.setattr(orchestrator_mod, "create_video_service", lambda settings: StubVideo(settings))
    monkeypatch.setattr(orchestrator_mod, "clear_confirm_event_redis", _noop_clear)

    orchestrator = GenerationOrchestrator(settings=test_settings, ws=ws, session=test_session)
    await orchestrator.run(
        project_id=project.id,
        run_id=run.id,
        request=GenerateRequest(),
        auto_mode=True,
    )

    await test_session.refresh(project)
    await test_session.refresh(run)
    assert project.status == "ready"
    assert project.video_url == "/static/videos/merged.mp4"
    assert run.status == "succeeded"

    res = await test_session.execute(select(Character).where(Character.project_id == project.id))
    assert len(res.scalars().all()) == 1

    res = await test_session.execute(select(Scene).where(Scene.project_id == project.id))
    assert len(res.scalars().all()) == 1

    res = await test_session.execute(
        select(Shot).join(Scene).where(Scene.project_id == project.id)
    )
    shots = res.scalars().all()
    assert len(shots) == 1
    assert shots[0].image_url
    assert shots[0].video_url
