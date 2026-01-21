from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class ImageService:
    """图像生成服务 (OpenAI 兼容接口)"""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _build_url(self) -> str:
        """构建完整的 API URL"""
        base = self.settings.image_base_url.rstrip("/")
        endpoint = self.settings.image_endpoint
        # 确保端点以 / 开头
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        return f"{base}{endpoint}"

    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        style: str | None = None,
    ) -> dict[str, Any]:
        """生成图像"""
        url = self._build_url()
        payload: dict[str, Any] = {
            "model": self.settings.image_model,
            "prompt": prompt,
            "size": size,
            "n": n,
        }
        if style:
            payload["style"] = style

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_s) as client:
            res = await client.post(url, headers=self.settings.image_headers(), json=payload)
            res.raise_for_status()
            return res.json()


class VideoService:
    """视频生成服务 (OpenAI 兼容接口)"""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _build_url(self) -> str:
        """构建完整的 API URL"""
        base = self.settings.video_base_url.rstrip("/")
        endpoint = self.settings.video_endpoint
        # 确保端点以 / 开头
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        return f"{base}{endpoint}"

    async def generate(
        self,
        prompt: str,
        duration: float = 5.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """生成视频"""
        url = self._build_url()
        payload: dict[str, Any] = {
            "model": self.settings.video_model,
            "prompt": prompt,
            "duration": duration,
            **kwargs,
        }

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_s) as client:
            res = await client.post(url, headers=self.settings.video_headers(), json=payload)
            res.raise_for_status()
            return res.json()


# 保留旧的 MediaService 作为兼容层
class MediaService:
    """媒体服务聚合类（兼容旧代码）"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.image = ImageService(settings)
        self.video = VideoService(settings)

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> dict[str, Any]:
        return await self.image.generate(prompt=prompt, size=size)

    async def generate_video(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        return await self.video.generate(prompt=prompt, **kwargs)

