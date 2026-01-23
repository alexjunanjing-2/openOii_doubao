from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import Settings
from app.services.llm import LLMService


class DummyMessage:
    def __init__(self):
        self.content = [
            SimpleNamespace(type="text", text="hello"),
            SimpleNamespace(type="tool_use", id="1", name="search", input={"q": "x"}),
        ]


class DummyStream:
    def __init__(self):
        self.text_stream = self._text_stream()

    async def _text_stream(self):
        yield "hello"
        yield " world"

    async def get_final_message(self):
        return DummyMessage()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyMessages:
    async def create(self, **kwargs):
        return DummyMessage()

    def stream(self, **kwargs):
        return DummyStream()


class DummyClient:
    def __init__(self):
        self.messages = DummyMessages()


def test_get_client_missing_credentials(monkeypatch):
    # 确保环境变量不干扰测试
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        anthropic_api_key=None,
        anthropic_auth_token=None
    )
    service = LLMService(settings)

    class MockAsyncAnthropic:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(service, "_import_anthropic", lambda: SimpleNamespace(AsyncAnthropic=MockAsyncAnthropic))

    with pytest.raises(ValueError, match="Anthropic credentials missing"):
        service._get_client()


@pytest.mark.asyncio
async def test_generate_parses_tool_calls(monkeypatch):
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", anthropic_api_key="key")
    service = LLMService(settings)
    monkeypatch.setattr(service, "_get_client", lambda: DummyClient())

    resp = await service.generate(messages=[{"role": "user", "content": "hi"}])
    assert resp.text == "hello"
    assert resp.tool_calls[0].name == "search"
    assert resp.tool_calls[0].input["q"] == "x"


@pytest.mark.asyncio
async def test_stream_emits_text_and_final(monkeypatch):
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", anthropic_api_key="key")
    service = LLMService(settings)
    monkeypatch.setattr(service, "_get_client", lambda: DummyClient())

    events = []
    async for event in service.stream(messages=[{"role": "user", "content": "hi"}]):
        events.append(event)

    assert events[0]["type"] == "text"
    assert events[-1]["type"] == "final"
