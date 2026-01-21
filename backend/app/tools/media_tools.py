from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.services.media_service import MediaService

from claude_agent_sdk import create_sdk_mcp_server, tool


def _tool_text(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": is_error}


@tool("generate_image", "Generate an image via OpenAI-compatible API", {"prompt": str, "size": str})
async def generate_image(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    service = MediaService(settings)
    prompt = args.get("prompt", "")
    size = args.get("size", "1024x1024")
    data = await service.generate_image(prompt=prompt, size=size)
    return _tool_text(str(data))


@tool("generate_video", "Generate a video via OpenAI-compatible API", {"prompt": str})
async def generate_video(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    service = MediaService(settings)
    prompt = args.get("prompt", "")
    data = await service.generate_video(prompt=prompt)
    return _tool_text(str(data))


def create_tools_mcp_server():
    server = create_sdk_mcp_server(name="openOii-media", version="0.1.0", tools=[generate_image, generate_video])
    return server
