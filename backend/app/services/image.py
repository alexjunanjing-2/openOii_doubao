from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.config import Settings
from app.services.file_cleaner import STATIC_DIR

logger = logging.getLogger(__name__)


class ImageService:
    """图像生成服务（支持多种 API 格式）"""

    def __init__(self, settings: Settings, *, max_retries: int = 3):
        self.settings = settings
        self.max_retries = max_retries
        self._cache_client: httpx.AsyncClient | None = None

    async def _get_cache_client(self) -> httpx.AsyncClient:
        """获取或创建用于缓存图片的 HTTP 客户端（连接复用）"""
        if self._cache_client is None or self._cache_client.is_closed:
            self._cache_client = httpx.AsyncClient(timeout=self.settings.request_timeout_s)
        return self._cache_client

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self._cache_client is not None and not self._cache_client.is_closed:
            await self._cache_client.aclose()
            self._cache_client = None

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

    async def cache_external_image(self, url: str) -> str:
        """缓存外部图片到本地静态目录，返回本地 URL。

        仅处理 http(s) URL，失败时返回原始 URL。
        """
        if not url or url.startswith(("/static/", "data:")):
            return url
        if not url.startswith(("http://", "https://")):
            return url

        content_type_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }

        try:
            client = await self._get_cache_client()
            res = await client.get(url)
            res.raise_for_status()
            content = res.content
            headers = res.headers

            content_type = headers.get("Content-Type", "").split(";")[0].strip().lower()
            ext = content_type_map.get(content_type)
            if not ext:
                suffix = Path(urlparse(url).path).suffix
                ext = suffix if suffix else ".png"

            static_dir = STATIC_DIR / "images"
            static_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{uuid4().hex}{ext}"
            save_path = static_dir / filename
            save_path.write_bytes(content)

            return f"/static/images/{filename}"
        except Exception as exc:
            logger.warning("Failed to cache external image, using original URL: %s", exc)
            return url

    async def download_and_save(self, url: str, save_path: Path) -> None:
        """从 URL 下载图片并保存到本地

        Args:
            url: 图片 URL
            save_path: 保存路径（完整路径，包含文件名）
        """
        from urllib.request import urlopen
        from urllib.error import HTTPError, URLError

        save_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading image from: {url[:100]}...")
        logger.debug(f"Full URL: {url}")
        logger.info(f"Saving to: {save_path}")

        try:
            # 使用 asyncio.to_thread 在线程池中运行同步的 urllib 代码
            def _download():
                try:
                    with urlopen(url, timeout=120) as response:
                        status = response.status
                        headers = dict(response.headers)

                        logger.info(f"Response status: {status}")
                        logger.debug(f"Response headers: {headers}")

                        if status != 200:
                            body = response.read().decode('utf-8', errors='ignore')
                            logger.error(f"Failed to download image. Status: {status}")
                            logger.error(f"Response body: {body[:500]}")
                            raise RuntimeError(f"Failed to download image (HTTP {status})")

                        # 检查内容类型
                        content_type = headers.get('Content-Type', '')
                        if not content_type.startswith('image/'):
                            logger.warning(f"Unexpected content type: {content_type}")

                        # 读取内容
                        content = response.read()
                        return content

                except HTTPError as e:
                    logger.error(f"HTTP error: {e.code} {e.reason}")
                    body = e.read().decode('utf-8', errors='ignore')
                    logger.error(f"Response body: {body[:500]}")
                    raise RuntimeError(f"Failed to download image (HTTP {e.code})") from e
                except URLError as e:
                    logger.error(f"URL error: {e.reason}")
                    raise RuntimeError(f"Failed to download image: {e.reason}") from e

            # 在线程池中执行下载
            content = await asyncio.to_thread(_download)

            # 保存文件
            with open(save_path, "wb") as f:
                f.write(content)

            logger.info(f"Successfully saved image ({len(content)} bytes)")

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error downloading image: {e}", exc_info=True)
            raise RuntimeError(f"Failed to download image: {str(e)[:100]}") from e

    async def _modelscope_generate(self, prompt: str) -> str:
        """ModelScope 异步图片生成"""
        base_url = self.settings.image_base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {self.settings.image_api_key}",
            "Content-Type": "application/json",
            "X-ModelScope-Async-Mode": "true",
        }

        timeout = httpx.Timeout(300.0, connect=30.0)

        print(f"[ImageService] 开始 ModelScope 图片生成")
        print(f"[ImageService] API地址: {base_url}/v1/images/generations")
        print(f"[ImageService] Headers: {headers}")

        async with httpx.AsyncClient(timeout=timeout) as client:
            # 1. 提交生成任务
            payload = {
                "model": self.settings.image_model,
                "prompt": prompt,
                "watermark": False,
            }

            print(f"[ImageService] 请求Body: {json.dumps(payload, ensure_ascii=False)}")

            res = await client.post(
                f"{base_url}/v1/images/generations",
                headers=headers,
                json=payload,
            )
            print(f"[ImageService] 提交任务响应状态码: {res.status_code}")
            print(f"[ImageService] 提交任务响应内容: {res.text}")
            res.raise_for_status()
            task_id = res.json().get("task_id")

            if not task_id:
                raise RuntimeError(f"ModelScope API did not return task_id: {res.json()}")

            print(f"[ImageService] 任务ID: {task_id}")

            # 2. 轮询任务状态
            poll_headers = {
                "Authorization": f"Bearer {self.settings.image_api_key}",
                "Content-Type": "application/json",
                "X-ModelScope-Task-Type": "image_generation",
            }

            max_polls = 60  # 最多轮询 60 次（5分钟）
            for poll_count in range(max_polls):
                result = await client.get(
                    f"{base_url}/v1/tasks/{task_id}",
                    headers=poll_headers,
                )
                result.raise_for_status()
                data = result.json()

                status = data.get("task_status")
                print(f"[ImageService] 轮询 {poll_count + 1}/{max_polls}: 任务状态 {status}")
                
                if status == "SUCCEED":
                    output_images = data.get("output_images", [])
                    if output_images:
                        print(f"[ImageService] 图片生成成功: {output_images[0]}")
                        return output_images[0]
                    raise RuntimeError(f"ModelScope task succeeded but no images: {data}")
                elif status == "FAILED":
                    print(f"[ImageService] ModelScope 图片生成失败: {data}")
                    raise RuntimeError(f"ModelScope image generation failed: {data}")

                # 等待 5 秒后继续轮询
                await asyncio.sleep(5)

            print(f"[ImageService] ModelScope 任务超时")
            raise RuntimeError(f"ModelScope task timeout after {max_polls * 5} seconds")

    async def _post_json_with_retry(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        delay_s = 0.5
        last_exc: Exception | None = None
        headers = self.settings.image_headers()

        print(f"[ImageService] 开始图片生成请求")
        print(f"[ImageService] API地址: {url}")
        print(f"[ImageService] Headers: {headers}")
        print(f"[ImageService] Body: {json.dumps(payload, ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_s) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    print(f"[ImageService] 第 {attempt + 1} 次尝试发送请求")
                    res = await client.post(url, headers=headers, json=payload)
                    print(f"[ImageService] 响应状态码: {res.status_code}")
                    if self._is_retryable_status(res.status_code) and attempt < self.max_retries:
                        print(f"[ImageService] 状态码 {res.status_code} 可重试，等待 {delay_s} 秒后重试")
                        await asyncio.sleep(delay_s)
                        delay_s = min(delay_s * 2, 8.0)
                        continue
                    res.raise_for_status()
                    result = res.json()
                    print(f"[ImageService] 请求成功，响应数据: {json.dumps(result, ensure_ascii=False)}")
                    return result
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                    last_exc = exc
                    print(f"[ImageService] 请求失败: {type(exc).__name__}: {exc}")
                    if attempt >= self.max_retries:
                        break
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    print(f"[ImageService] 响应状态码: {status}")
                    if isinstance(status, int) and not self._is_retryable_status(status):
                        break
                    await asyncio.sleep(delay_s)
                    delay_s = min(delay_s * 2, 8.0)

        print(f"[ImageService] 图片生成请求失败，已重试 {self.max_retries} 次，最终错误: {last_exc}")
        raise RuntimeError(f"Image generation request failed after retries: {last_exc}") from last_exc

    async def _post_stream_with_retry(self, url: str, payload: dict[str, Any]) -> str:
        """流式请求，收集所有 chunk 并提取最终 URL"""
        delay_s = 0.5
        last_exc: Exception | None = None
        headers = self.settings.image_headers()

        print(f"[ImageService] 开始流式图片生成请求")
        print(f"[ImageService] API地址: {url}")
        print(f"[ImageService] Headers: {headers}")
        print(f"[ImageService] Body: {json.dumps(payload, ensure_ascii=False)}")

        timeout = httpx.Timeout(300.0, connect=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    print(f"[ImageService] 第 {attempt + 1} 次尝试发送流式请求")
                    collected_content = ""
                    async with client.stream(
                        "POST", url, headers=headers, json=payload
                    ) as res:
                        print(f"[ImageService] 流式响应状态码: {res.status_code}")
                        if self._is_retryable_status(res.status_code) and attempt < self.max_retries:
                            print(f"[ImageService] 状态码 {res.status_code} 可重试，等待 {delay_s} 秒后重试")
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
                                    print(f"[ImageService] 流式响应错误: {chunk['error']}")
                                    raise RuntimeError(f"Stream error: {chunk['error']}")
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    # 收集 content 和 reasoning_content
                                    content = delta.get("content", "")
                                    reasoning_content = delta.get("reasoning_content", "")
                                    if content:
                                        collected_content += content
                                    if reasoning_content:
                                        collected_content += reasoning_content
                            except json.JSONDecodeError as e:
                                if "error" in data_str:
                                    try:
                                        err = json.loads(data_str)
                                        print(f"[ImageService] 流式响应错误: {err}")
                                        raise RuntimeError(f"Stream error: {err}")
                                    except json.JSONDecodeError:
                                        logger.debug("Non-JSON error line in stream: %s", data_str[:100])
                                else:
                                    logger.debug("Skipping non-JSON line in image stream: %s", e)
                                continue

                    print(f"[ImageService] 流式请求成功，收集到的内容: {collected_content}")
                    return collected_content

                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                    last_exc = exc
                    print(f"[ImageService] 流式请求失败: {type(exc).__name__}: {exc}")
                    if attempt >= self.max_retries:
                        break
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    print(f"[ImageService] 响应状态码: {status}")
                    if isinstance(status, int) and not self._is_retryable_status(status):
                        break
                    await asyncio.sleep(delay_s)
                    delay_s = min(delay_s * 2, 8.0)

        print(f"[ImageService] 流式图片生成请求失败，已重试 {self.max_retries} 次，最终错误: {last_exc}")
        raise RuntimeError(f"Image generation stream failed after retries: {last_exc}") from last_exc

    async def generate(
        self,
        *,
        prompt: str,
        size: str = "1024x1024",
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
                "watermark": False,
                **kwargs,
            }
        else:
            payload: dict[str, Any] = {
                "model": self.settings.image_model,
                "prompt": prompt,
                "size": self.settings.storyboard_image_size,
                "watermark": False,
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
        image_urls: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        # ModelScope API（异步轮询模式）
        if self._is_modelscope_api():
            if image_urls:
                logger.info(
                    "Image URLs provided but ModelScope backend does not support it; falling back to text-to-image"
                )
            return await self._modelscope_generate(prompt)

        url = self._build_url()

        # 图生图（I2I）：仅在启用开关且提供参考图时尝试
        print(f"[ImageService] image_urls: {image_urls}")
        print(f"[ImageService] use_i2i(): {self.settings.use_i2i()}")
        print(f"[ImageService] enable_image_to_image: {self.settings.enable_image_to_image}")
        if image_urls and self.settings.use_i2i():
            try:
                # Chat Completions 风格（多模态）
                if "/chat/completions" in self.settings.image_endpoint:
                    content_list = [{"type": "text", "text": prompt}]
                    for img_url in image_urls:
                        if img_url.startswith(("http://", "https://")):
                            content_list.append({
                                "type": "image_url",
                                "image_url": {"url": img_url},
                            })
                        elif img_url.startswith("/static/"):
                            public_url = self.settings.build_public_url(img_url)
                            if public_url:
                                content_list.append({
                                    "type": "image_url",
                                    "image_url": {"url": public_url},
                                })
                            else:
                                content_list.append({
                                    "type": "image_url",
                                    "image_url": {"url": img_url},
                                })

                    payload: dict[str, Any] = {
                        "model": self.settings.image_model,
                        "messages": [
                            {
                                "role": "user",
                                "content": content_list,
                            }
                        ],
                        "stream": True,
                        "watermark": False,
                        **kwargs,
                    }
                    content = await self._post_stream_with_retry(url, payload)

                    extracted = self._extract_url_from_text(content)
                    if extracted:
                        return extracted
                    raise RuntimeError(f"Image API stream response missing URL: {content}")
                else:
                    # 标准图片生成接口（图生图）
                    # 直接传递图片 URL 列表
                    public_image_urls = []
                    for img_url in image_urls:
                        if img_url.startswith("/static/"):
                            public_url = self.settings.build_public_url(img_url)
                            public_image_urls.append(public_url if public_url else img_url)
                        else:
                            public_image_urls.append(img_url)

                    payload = {
                        "model": self.settings.image_model,
                        "prompt": prompt,
                        "size": "2K",
                        "image": public_image_urls,
                        "watermark": False,
                        **kwargs,
                    }
                    data = await self._post_json_with_retry(url, payload)
                    items = data.get("data") or []
                    if isinstance(items, list) and items:
                        first = items[0] if isinstance(items[0], dict) else {}
                        result_url = first.get("url")
                        if isinstance(result_url, str) and result_url:
                            return self._sanitize_url(result_url)

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
                "watermark": False,
                **kwargs,
            }
            content = await self._post_stream_with_retry(url, payload)

            extracted = self._extract_url_from_text(content)
            if extracted:
                return extracted
            raise RuntimeError(f"Image API stream response missing URL: {content}")

        # DALL-E 风格（非流式）
        data = await self.generate(prompt=prompt, size=size, response_format="url", **kwargs)
        items = data.get("data") or []
        if isinstance(items, list) and items:
            first = items[0] if isinstance(items[0], dict) else {}
            result_url = first.get("url")
            if isinstance(result_url, str) and result_url:
                return self._sanitize_url(result_url)

        raise RuntimeError(f"Image API response missing URL: {data}")
