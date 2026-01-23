from __future__ import annotations

import pytest

from app.agents.orchestrator import GenerationOrchestrator
from app.config import Settings


class MockWsManager:
    def __init__(self):
        self.events = []

    async def send_event(self, project_id: int, event: dict):
        self.events.append((project_id, event))


class TestAgentIndex:
    @pytest.fixture
    def orchestrator(self):
        settings = Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            anthropic_api_key="test",
            image_api_key="test",
            video_api_key="test",
        )
        ws = MockWsManager()
        return GenerationOrchestrator(settings=settings, ws=ws, session=None)

    def test_valid_agent_indices(self, orchestrator):
        assert orchestrator._agent_index("onboarding") == 0
        assert orchestrator._agent_index("director") == 1
        assert orchestrator._agent_index("scriptwriter") == 2
        assert orchestrator._agent_index("character_artist") == 3
        assert orchestrator._agent_index("storyboard_artist") == 4
        assert orchestrator._agent_index("video_generator") == 5
        assert orchestrator._agent_index("video_merger") == 6
        assert orchestrator._agent_index("review") == 7

    def test_invalid_agent_raises(self, orchestrator):
        with pytest.raises(ValueError, match="Unknown agent"):
            orchestrator._agent_index("invalid")
