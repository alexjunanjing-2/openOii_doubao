from __future__ import annotations

import json

import pytest

from app.agents.orchestrator import GenerationOrchestrator
from app.config import Settings


class MockWsManager:
    def __init__(self):
        self.events = []

    async def send_event(self, project_id: int, event: dict):
        self.events.append((project_id, event))


class TestParseNextAgent:
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

    def test_valid_next_agent(self, orchestrator):
        route = json.dumps({"next_agent": "character", "reason": "test"})
        result = orchestrator._parse_next_agent(route)
        assert result == "character"

    def test_none_next_agent(self, orchestrator):
        route = json.dumps({"next_agent": "none", "reason": "all good"})
        result = orchestrator._parse_next_agent(route)
        assert result is None

    def test_empty_next_agent(self, orchestrator):
        route = json.dumps({"next_agent": "", "reason": "test"})
        result = orchestrator._parse_next_agent(route)
        assert result is None

    def test_invalid_agent_name(self, orchestrator):
        route = json.dumps({"next_agent": "invalid_agent", "reason": "test"})
        result = orchestrator._parse_next_agent(route)
        assert result is None

    def test_null_route_decision(self, orchestrator):
        result = orchestrator._parse_next_agent(None)
        assert result is None

    def test_empty_route_decision(self, orchestrator):
        result = orchestrator._parse_next_agent("")
        assert result is None

    def test_invalid_json(self, orchestrator):
        result = orchestrator._parse_next_agent("not json")
        assert result is None

    def test_missing_next_agent_key(self, orchestrator):
        route = json.dumps({"reason": "test"})
        result = orchestrator._parse_next_agent(route)
        assert result is None

    def test_all_valid_agents(self, orchestrator):
        valid_agents = ["onboarding", "director", "scriptwriter", "character", "storyboard", "review"]
        for agent in valid_agents:
            route = json.dumps({"next_agent": agent})
            result = orchestrator._parse_next_agent(route)
            assert result == agent

    def test_whitespace_trimmed(self, orchestrator):
        route = json.dumps({"next_agent": "  character  "})
        result = orchestrator._parse_next_agent(route)
        assert result == "character"


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
        assert orchestrator._agent_index("character") == 3
        assert orchestrator._agent_index("storyboard") == 4
        assert orchestrator._agent_index("review") == 5

    def test_invalid_agent_raises(self, orchestrator):
        with pytest.raises(ValueError, match="Unknown agent"):
            orchestrator._agent_index("invalid")
