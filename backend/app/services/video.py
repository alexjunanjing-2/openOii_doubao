from __future__ import annotations

import asyncio
import base64
import json
import re
from typing import Any

import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class VideoService:
    """视频生成服务（OpenAI 兼容接口，支持流式模式和图生视频）"""

    def __init__(self, settings: Settings, *, max_retries: int = 3):
        self.settings = settings
        self.max_retries = max_retries

    def _build_url(self) -> str:
        base = self.settings.video_base_url.rstrip("/")
        endpoint = self.settings.video_endpoint
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        return f"{base}{endpoint}"

    def _is_retryable_status(self, status_code: int) -> bool:
        return status_code in {408, 429, 500, 502, 503, 504}

    def _sanitize_url(self, url: str) -> str:
        cleaned = url.strip().strip("\"'")
        return cleaned.rstrip(").,;]}>")

    def _extract_url_from_text(self, text: str) -> str | None:
        if not text or not isinstance(text, str):
            return None
        candidate = text.strip()
        if candidate.startswith("data:"):
            return candidate
        if candidate.startswith(("http://", "https://")):
            return self._sanitize_url(candidate)
        urls = re.findall(r"https?://[^\s<>\"]+", candidate)
        if urls:
            return self._sanitize_url(urls[0])
        return None

    async def _post_json_with_retry(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = self.settings.video_headers()
        print(f"[VideoService] 开始JSON请求，URL: {url}")
        print(f"[VideoService] 请求 Headers: {json.dumps(headers, ensure_ascii=False)}")
        print(f"[VideoService] 请求 Body: {json.dumps(payload, ensure_ascii=False)}")
        delay_s = 0.5
        last_exc: Exception | None = None

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_s) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    res = await client.post(url, headers=headers, json=payload)
                    print(f"[VideoService] 响应状态码: {res.status_code}")
                    if self._is_retryable_status(res.status_code) and attempt < self.max_retries:
                        print(f"[VideoService] 状态码 {res.status_code} 可重试，等待 {delay_s} 秒后重试")
                        await asyncio.sleep(delay_s)
                        delay_s = min(delay_s * 2, 8.0)
                        continue
                    res.raise_for_status()
                    result = res.json()
                    print(f"[VideoService] 请求成功，响应数据: {json.dumps(result, ensure_ascii=False)[:200]}")
                    return result
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                    last_exc = exc
                    print(f"[VideoService] 请求失败: {type(exc).__name__}: {exc}")
                    if attempt >= self.max_retries:
                        break
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    print(f"[VideoService] 响应状态码: {status}")
                    if isinstance(status, int) and not self._is_retryable_status(status):
                        break
                    print(f"[VideoService] 等待 {delay_s} 秒后重试")
                    await asyncio.sleep(delay_s)
                    delay_s = min(delay_s * 2, 8.0)

        print(f"[VideoService] 请求失败，已重试 {self.max_retries} 次，最终错误: {last_exc}")
        raise RuntimeError(f"Video generation request failed after retries: {last_exc}") from last_exc

    async def _post_stream_with_retry(self, url: str, payload: dict[str, Any]) -> str:
        """流式请求，收集所有 chunk 并提取最终 URL"""
        headers = self.settings.video_headers()
        print(f"[VideoService] 开始流式请求，URL: {url}")
        print(f"[VideoService] 请求 Headers: {json.dumps(headers, ensure_ascii=False)}")
        print(f"[VideoService] 请求 Body: {json.dumps(payload, ensure_ascii=False)}")
        delay_s = 0.5
        last_exc: Exception | None = None

        # 视频生成需要更长的超时时间
        timeout = httpx.Timeout(600.0, connect=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    print(f"[VideoService] 第 {attempt + 1} 次尝试发送流式请求")
                    collected_content = ""
                    async with client.stream(
                        "POST", url, headers=headers, json=payload
                    ) as res:
                        print(f"[VideoService] 流式响应状态码: {res.status_code}")
                        if self._is_retryable_status(res.status_code) and attempt < self.max_retries:
                            print(f"[VideoService] 状态码 {res.status_code} 可重试，等待 {delay_s} 秒后重试")
                            await asyncio.sleep(delay_s)
                            delay_s = min(delay_s * 2, 8.0)
                            continue
                        res.raise_for_status()

                        async for line in res.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:]  # 去掉 "data: " 前缀
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                # 检查是否有错误
                                if "error" in chunk:
                                    print(f"[VideoService] 流式响应错误: {chunk['error']}")
                                    raise RuntimeError(f"Stream error: {chunk['error']}")
                                # 提取 content
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        collected_content += content
                            except json.JSONDecodeError as e:
                                # 可能是非 JSON 行，检查是否包含错误
                                if "error" in data_str:
                                    try:
                                        err = json.loads(data_str)
                                        print(f"[VideoService] 流式响应错误: {err}")
                                        raise RuntimeError(f"Stream error: {err}")
                                    except json.JSONDecodeError:
                                        logger.debug("Non-JSON error line in stream: %s", data_str[:100])
                                else:
                                    logger.debug("Skipping non-JSON line in video stream: %s", e)
                                continue

                    print(f"[VideoService] 流式请求成功，收集到的内容长度: {len(collected_content)}")
                    return collected_content

                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                    last_exc = exc
                    print(f"[VideoService] 流式请求失败: {type(exc).__name__}: {exc}")
                    if attempt >= self.max_retries:
                        break
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    print(f"[VideoService] 响应状态码: {status}")
                    if isinstance(status, int) and not self._is_retryable_status(status):
                        break
                    print(f"[VideoService] 等待 {delay_s} 秒后重试")
                    await asyncio.sleep(delay_s)
                    delay_s = min(delay_s * 2, 8.0)

        print(f"[VideoService] 流式请求失败，已重试 {self.max_retries} 次，最终错误: {last_exc}")
        raise RuntimeError(f"Video generation stream failed after retries: {last_exc}") from last_exc

    async def generate(
        self,
        *,
        prompt: str,
        duration: float = 5.0,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        url = self._build_url()

        if "/chat/completions" in self.settings.video_endpoint:
            payload: dict[str, Any] = {
                "model": self.settings.video_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": stream,
                **kwargs,
            }
        else:
            payload: dict[str, Any] = {
                "model": self.settings.video_model,
                "prompt": prompt,
                "duration": duration,
                **kwargs,
            }

        return await self._post_json_with_retry(url, payload)

    async def generate_url(self, *, prompt: str, image_bytes: bytes | None = None, **kwargs: Any) -> str:
        """生成视频并返回 URL

        Args:
            prompt: 文本提示词
            image_bytes: 参考图片字节流（图生视频模式）
            **kwargs: 其他参数

        Returns:
            视频 URL
        """
        url = self._build_url()

        # 图生视频模式
        if image_bytes and self.settings.use_i2v():
            # 将图片转换为 base64
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # Chat Completions 风格（图生视频）
            if "/chat/completions" in self.settings.video_endpoint:
                payload: dict[str, Any] = {
                    "model": self.settings.video_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    "stream": True,
                    **kwargs,
                }
                content = await self._post_stream_with_retry(url, payload)

                extracted = self._extract_url_from_text(content)
                if extracted:
                    return extracted
                raise RuntimeError(f"Video API stream response missing URL: {content}")
            else:
                # 标准视频生成接口（图生视频）
                payload: dict[str, Any] = {
                    "model": self.settings.video_model,
                    "prompt": prompt,
                    "image": image_base64,
                    **kwargs,
                }
                data = await self._post_json_with_retry(url, payload)
                items = data.get("data") or []
                if isinstance(items, list) and items:
                    first = items[0] if isinstance(items[0], dict) else {}
                    result_url = first.get("url")
                    if isinstance(result_url, str) and result_url:
                        return self._sanitize_url(result_url)

                raise RuntimeError(f"Video API response missing URL: {data}")

        # 文生视频模式（原有逻辑）
        # Chat Completions 风格需要流式模式
        if "/chat/completions" in self.settings.video_endpoint:
            payload: dict[str, Any] = {
                "model": self.settings.video_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                **kwargs,
            }
            content = await self._post_stream_with_retry(url, payload)

            extracted = self._extract_url_from_text(content)
            if extracted:
                return extracted
            raise RuntimeError(f"Video API stream response missing URL: {content}")
        else:
            # 标准视频生成接口（非流式）
            data = await self.generate(prompt=prompt, **kwargs)
            items = data.get("data") or []
            if isinstance(items, list) and items:
                first = items[0] if isinstance(items[0], dict) else {}
                result_url = first.get("url")
                if isinstance(result_url, str) and result_url:
                    return self._sanitize_url(result_url)

            raise RuntimeError(f"Video API response missing URL: {data}")

    async def merge_urls(self, video_urls: list[str]) -> str:
        """拼接多个视频 URL

        使用 ffmpeg 将多个视频片段拼接成一个完整视频。

        Args:
            video_urls: 要拼接的视频 URL 列表

        Returns:
            拼接后的视频 URL（本地路径）
        """
        if not video_urls:
            raise RuntimeError("No video URLs provided for merging")

        from app.services.video_merger import get_video_merger_service

        merger = get_video_merger_service()
        return await merger.merge_videos(video_urls)
