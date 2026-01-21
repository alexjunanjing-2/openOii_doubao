from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class ImageService:
    """图像生成服务（支持多种 API 格式）"""

    def __init__(self, settings: Settings, *, max_retries: int = 3):
        self.settings = settings
        self.max_retries = max_retries

    def _build_url(self) -> str:
        base = self.settings.image_base_url.rstrip("/")
        endpoint = self.settings.image_endpoint
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        return f"{base}{endpoint}"

    def _is_retryable_status(self, status_code: int) -> bool:
        return status_code in {408, 429, 500, 502, 503, 504}

    def _is_modelscope_api(self) -> bool:
        """检测是否是 ModelScope API"""
        return "modelscope" in self.settings.image_base_url.lower()

    async def _modelscope_generate(self, prompt: str) -> str:
        """ModelScope 异步图片生成"""
        base_url = self.settings.image_base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {self.settings.image_api_key}",
            "Content-Type": "application/json",
            "X-ModelScope-Async-Mode": "true",
        }

        timeout = httpx.Timeout(300.0, connect=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            # 1. 提交生成任务
            payload = {
                "model": self.settings.image_model,
                "prompt": prompt,
            }

            res = await client.post(
                f"{base_url}/v1/images/generations",
                headers=headers,
                json=payload,
            )
            res.raise_for_status()
            task_id = res.json().get("task_id")

            if not task_id:
                raise RuntimeError(f"ModelScope API did not return task_id: {res.json()}")

            # 2. 轮询任务状态
            poll_headers = {
                "Authorization": f"Bearer {self.settings.image_api_key}",
                "Content-Type": "application/json",
                "X-ModelScope-Task-Type": "image_generation",
            }

            max_polls = 60  # 最多轮询 60 次（5分钟）
            for _ in range(max_polls):
                result = await client.get(
                    f"{base_url}/v1/tasks/{task_id}",
                    headers=poll_headers,
                )
                result.raise_for_status()
                data = result.json()

                status = data.get("task_status")
                if status == "SUCCEED":
                    output_images = data.get("output_images", [])
                    if output_images:
                        return output_images[0]
                    raise RuntimeError(f"ModelScope task succeeded but no images: {data}")
                elif status == "FAILED":
                    raise RuntimeError(f"ModelScope image generation failed: {data}")

                # 等待 5 秒后继续轮询
                await asyncio.sleep(5)

            raise RuntimeError(f"ModelScope task timeout after {max_polls * 5} seconds")

    async def _post_json_with_retry(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        delay_s = 0.5
        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_s) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    res = await client.post(url, headers=self.settings.image_headers(), json=payload)
                    if self._is_retryable_status(res.status_code) and attempt < self.max_retries:
                        await asyncio.sleep(delay_s)
                        delay_s = min(delay_s * 2, 8.0)
                        continue
                    res.raise_for_status()
                    return res.json()
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                    last_exc = exc
                    if attempt >= self.max_retries:
                        break
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if isinstance(status, int) and not self._is_retryable_status(status):
                        break
                    await asyncio.sleep(delay_s)
                    delay_s = min(delay_s * 2, 8.0)

        raise RuntimeError(f"Image generation request failed after retries: {last_exc}") from last_exc

    async def _post_stream_with_retry(self, url: str, payload: dict[str, Any]) -> str:
        """流式请求，收集所有 chunk 并提取最终 URL"""
        delay_s = 0.5
        last_exc: Exception | None = None

        timeout = httpx.Timeout(300.0, connect=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    collected_content = ""
                    async with client.stream(
                        "POST", url, headers=self.settings.image_headers(), json=payload
                    ) as res:
                        if self._is_retryable_status(res.status_code) and attempt < self.max_retries:
                            await asyncio.sleep(delay_s)
                            delay_s = min(delay_s * 2, 8.0)
                            continue
                        res.raise_for_status()

                        async for line in res.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                if "error" in chunk:
                                    raise RuntimeError(f"Stream error: {chunk['error']}")
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        collected_content += content
                            except json.JSONDecodeError:
                                if "error" in data_str:
                                    try:
                                        err = json.loads(data_str)
                                        raise RuntimeError(f"Stream error: {err}")
                                    except json.JSONDecodeError:
                                        pass
                                continue

                    return collected_content

                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                    last_exc = exc
                    if attempt >= self.max_retries:
                        break
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if isinstance(status, int) and not self._is_retryable_status(status):
                        break
                    await asyncio.sleep(delay_s)
                    delay_s = min(delay_s * 2, 8.0)

        raise RuntimeError(f"Image generation stream failed after retries: {last_exc}") from last_exc

    async def generate(
        self,
        *,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        style: str | None = None,
        response_format: str = "url",
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        url = self._build_url()

        if "/chat/completions" in self.settings.image_endpoint:
            payload: dict[str, Any] = {
                "model": self.settings.image_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": stream,
                **kwargs,
            }
        else:
            payload: dict[str, Any] = {
                "model": self.settings.image_model,
                "prompt": prompt,
                "size": size,
                "n": n,
                "response_format": response_format,
                **kwargs,
            }
            if style:
                payload["style"] = style

        return await self._post_json_with_retry(url, payload)

    async def generate_url(
        self,
        *,
        prompt: str,
        size: str = "1024x1024",
        image_bytes: bytes | None = None,
        **kwargs: Any,
    ) -> str:
        # ModelScope API（异步轮询模式）
        if self._is_modelscope_api():
            if image_bytes is not None:
                logger.info(
                    "I2I reference image provided but ModelScope backend does not support it; falling back to text-to-image"
                )
            return await self._modelscope_generate(prompt)

        url = self._build_url()

        # 图生图（I2I）：仅在启用开关且提供参考图时尝试
        if image_bytes is not None and self.settings.use_i2i():
            try:
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")

                # Chat Completions 风格（多模态）
                if "/chat/completions" in self.settings.image_endpoint:
                    payload: dict[str, Any] = {
                        "model": self.settings.image_model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                                    },
                                ],
                            }
                        ],
                        "stream": True,
                        **kwargs,
                    }
                    content = await self._post_stream_with_retry(url, payload)

                    if isinstance(content, str) and content.strip():
                        if content.startswith(("http://", "https://", "data:")):
                            return content.strip()
                        urls = re.findall(r'https?://[^\s<>"]+', content)
                        if urls:
                            return urls[0]
                        return content.strip()

                    raise RuntimeError(f"Image API stream response missing URL: {content}")
                else:
                    # 标准图片生成接口（图生图）
                    payload = {
                        "model": self.settings.image_model,
                        "prompt": prompt,
                        "size": size,
                        "n": 1,
                        "response_format": "url",
                        "image": image_base64,
                        **kwargs,
                    }
                    data = await self._post_json_with_retry(url, payload)
                    items = data.get("data") or []
                    if isinstance(items, list) and items:
                        first = items[0] if isinstance(items[0], dict) else {}
                        result_url = first.get("url")
                        if isinstance(result_url, str) and result_url:
                            return result_url

                    raise RuntimeError(f"Image API response missing URL: {data}")
            except Exception as exc:
                # 降级：I2I 失败自动回退到文生图
                logger.warning(
                    "Image-to-image failed, falling back to text-to-image: %s",
                    exc,
                    exc_info=True,
                )

        # 文生图（原有逻辑）
        # Chat Completions 风格（流式模式）
        if "/chat/completions" in self.settings.image_endpoint:
            payload = {
                "model": self.settings.image_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                **kwargs,
            }
            content = await self._post_stream_with_retry(url, payload)

            if isinstance(content, str) and content.strip():
                if content.startswith(("http://", "https://", "data:")):
                    return content.strip()
                urls = re.findall(r'https?://[^\s<>"]+', content)
                if urls:
                    return urls[0]
                return content.strip()

            raise RuntimeError(f"Image API stream response missing URL: {content}")

        # DALL-E 风格（非流式）
        data = await self.generate(prompt=prompt, size=size, response_format="url", **kwargs)
        items = data.get("data") or []
        if isinstance(items, list) and items:
            first = items[0] if isinstance(items[0], dict) else {}
            result_url = first.get("url")
            if isinstance(result_url, str) and result_url:
                return result_url

        raise RuntimeError(f"Image API response missing URL: {data}")

