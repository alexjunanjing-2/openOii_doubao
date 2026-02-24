from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx
from app.config import Settings


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(slots=True)
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    raw: Any


class LLMService:
    """Claude (Anthropic Messages API) 服务包装器。

    - 直接使用 `anthropic` SDK（不是 claude_agent_sdk）
    - 支持工具调用（tools/tool_choice）
    - 支持流式输出
    """

    def __init__(self, settings: Settings, *, max_retries: int = 3):
        self.settings = settings
        self.max_retries = max_retries
        self._client: Any | None = None
        self._anthropic: Any | None = None

    def _import_anthropic(self) -> Any:
        if self._anthropic is not None:
            return self._anthropic
        try:
            import anthropic  # type: ignore
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "Missing dependency `anthropic`. Install optional deps: `uv sync --extra agents` "
                "or `pip install 'openOii-backend[agents]'`."
            ) from exc
        self._anthropic = anthropic
        return anthropic

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        anthropic = self._import_anthropic()

        api_key = self.settings.anthropic_api_key or self.settings.anthropic_auth_token
        if not api_key:
            raise ValueError("Anthropic credentials missing: set `anthropic_api_key` or `anthropic_auth_token`.")

        default_headers: dict[str, str] = {}
        if self.settings.anthropic_auth_token:
            default_headers["Authorization"] = f"Bearer {self.settings.anthropic_auth_token}"

        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": self.settings.request_timeout_s,
            "max_retries": 0,
        }
        if self.settings.anthropic_base_url:
            kwargs["base_url"] = self.settings.anthropic_base_url
        if default_headers:
            kwargs["default_headers"] = default_headers

        self._client = anthropic.AsyncAnthropic(**kwargs)
        return self._client

    def _parse_message(self, message: Any) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in getattr(message, "content", []) or []:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(getattr(block, "text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=str(getattr(block, "id", "")),
                        name=str(getattr(block, "name", "")),
                        input=dict(getattr(block, "input", {}) or {}),
                    )
                )

        return LLMResponse(text="".join(text_parts), tool_calls=tool_calls, raw=message)

    def _is_retryable_error(self, exc: Exception) -> bool:
        anthropic = self._import_anthropic()
        retryable_types: tuple[type[BaseException], ...] = (
            getattr(anthropic, "RateLimitError", Exception),
            getattr(anthropic, "APIConnectionError", Exception),
            getattr(anthropic, "APITimeoutError", Exception),
        )
        if isinstance(exc, retryable_types):
            return True

        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int) and status_code in {408, 429, 500, 502, 503, 504}:
            return True

        return False

    async def generate(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        print(f"[LLMService] 开始生成请求，model={model or self.settings.anthropic_model}, max_tokens={max_tokens}")
        client = self._get_client()

        payload: dict[str, Any] = {
            "model": model or self.settings.anthropic_model,
            "max_tokens": max_tokens,
            "messages": messages,
            **kwargs,
        }
        if system is not None:
            payload["system"] = system
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature

        print(f"[LLMService] 请求参数：messages={len(messages)}, system={bool(system)}, tools={bool(tools)}")
        delay_s = 0.5
        for attempt in range(self.max_retries + 1):
            try:
                print(f"[LLMService] 第 {attempt + 1} 次尝试发送请求")
                message = await client.messages.create(**payload)
                print(f"[LLMService] 请求成功，响应类型: {type(message).__name__}")
                return self._parse_message(message)
            except Exception as exc:
                print(f"[LLMService] 请求失败: {type(exc).__name__}: {exc}")
                if attempt >= self.max_retries or not self._is_retryable_error(exc):
                    raise
                print(f"[LLMService] 等待 {delay_s} 秒后重试")
                await asyncio.sleep(delay_s)
                delay_s = min(delay_s * 2, 8.0)

        raise RuntimeError("unreachable")  # pragma: no cover

    async def stream(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式输出。

        产出事件：
        - {"type": "text", "text": "..."}  # 增量文本
        - {"type": "final", "response": LLMResponse(...)}  # 最终聚合（包含 tool_calls）
        """
        print(f"[LLMService] 开始流式生成请求，model={model or self.settings.anthropic_model}, max_tokens={max_tokens}")
        client = self._get_client()

        payload: dict[str, Any] = {
            "model": model or self.settings.anthropic_model,
            "max_tokens": max_tokens,
            "messages": messages,
            **kwargs,
        }
        if system is not None:
            payload["system"] = system
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature

        print(f"[LLMService] 流式请求参数：messages={len(messages)}, system={bool(system)}, tools={bool(tools)}")
        delay_s = 0.5
        for attempt in range(self.max_retries + 1):
            try:
                print(f"[LLMService] 第 {attempt + 1} 次尝试发送流式请求")
                async with client.messages.stream(**payload) as stream:
                    text_stream = getattr(stream, "text_stream", None)
                    if text_stream is not None:
                        async for text in text_stream:
                            yield {"type": "text", "text": text}
                    else:  # pragma: no cover
                        async for event in stream:
                            event_type = getattr(event, "type", None)
                            if event_type == "text":
                                yield {"type": "text", "text": getattr(event, "text", "")}
                            elif event_type == "content_block_delta":
                                delta = getattr(event, "delta", None)
                                delta_text = getattr(delta, "text", None)
                                if isinstance(delta_text, str):
                                    yield {"type": "text", "text": delta_text}

                    final_message = await stream.get_final_message()
                    print(f"[LLMService] 流式请求成功，最终响应类型: {type(final_message).__name__}")
                    yield {"type": "final", "response": self._parse_message(final_message)}
                return
            except Exception as exc:
                print(f"[LLMService] 流式请求失败: {type(exc).__name__}: {exc}")
                if attempt >= self.max_retries or not self._is_retryable_error(exc):
                    raise
                print(f"[LLMService] 等待 {delay_s} 秒后重试")
                await asyncio.sleep(delay_s)
                delay_s = min(delay_s * 2, 8.0)

        raise RuntimeError("unreachable")  # pragma: no cover


class DoubaoLLMService:
    """豆包 LLM 服务（火山引擎 Ark API）。

    - 使用 OpenAI 兼容接口
    - 支持工具调用（tools/tool_choice）
    - 支持流式输出
    """

    def __init__(self, settings: Settings, *, max_retries: int = 3):
        self.settings = settings
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client

        api_key = self.settings.DOUBAO_API_KEY
        if not api_key:
            raise ValueError("Doubao LLM credentials missing: set `DOUBAO_API_KEY`.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": self.settings.app_name,
        }

        self._client = httpx.AsyncClient(
            base_url=self.settings.doubao_llm_base_url,
            headers=headers,
            timeout=self.settings.request_timeout_s,
        )
        return self._client

    def _parse_tool_calls(self, tool_calls_data: list[dict[str, Any]]) -> list[ToolCall]:
        """解析豆包格式的工具调用"""
        tool_calls: list[ToolCall] = []
        for tc in tool_calls_data:
            function = tc.get("function", {})
            name = function.get("name", "")
            arguments_str = function.get("arguments", "{}")
            
            try:
                arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
            except json.JSONDecodeError:
                arguments = {}
            
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=name,
                    input=arguments,
                )
            )
        return tool_calls

    def _parse_response(self, response_data: dict[str, Any]) -> LLMResponse:
        """解析豆包响应"""
        choices = response_data.get("choices", [])
        if not choices:
            return LLMResponse(text="", tool_calls=[], raw=response_data)
        
        choice = choices[0]
        message = choice.get("message", {})
        
        text = message.get("content", "") or ""
        tool_calls = self._parse_tool_calls(message.get("tool_calls", []))
        
        return LLMResponse(text=text, tool_calls=tool_calls, raw=response_data)

    def _is_retryable_error(self, exc: Exception) -> bool:
        if isinstance(exc, httpx.TimeoutException):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            if status_code in {408, 429, 500, 502, 503, 504}:
                return True
        return False

    async def generate(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        print(f"[DoubaoLLMService] 开始生成请求，model={model or self.settings.doubao_llm_model}, max_tokens={max_tokens}")
        client = self._get_client()

        payload: dict[str, Any] = {
            "model": model or self.settings.doubao_llm_model,
            "max_tokens": max_tokens,
            "messages": messages,
            "stream": False,
            "thinking": {"type": "disabled"},
            **kwargs,
        }
        
        if system is not None:
            payload["messages"].insert(0, {"role": "system", "content": system})
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature

        print(f"[DoubaoLLMService] 请求参数：messages={len(messages)}, system={bool(system)}, tools={bool(tools)}")
        delay_s = 0.5
        for attempt in range(self.max_retries + 1):
            try:
                print(f"[DoubaoLLMService] 第 {attempt + 1} 次尝试发送请求")
                response = await client.post(
                    self.settings.doubao_llm_endpoint,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                print(f"[DoubaoLLMService] 请求成功，响应数据: {json.dumps(data, ensure_ascii=False)[:200]}")
                return self._parse_response(data)
            except Exception as exc:
                print(f"[DoubaoLLMService] 请求失败: {type(exc).__name__}: {exc}")
                if attempt >= self.max_retries or not self._is_retryable_error(exc):
                    raise
                print(f"[DoubaoLLMService] 等待 {delay_s} 秒后重试")
                await asyncio.sleep(delay_s)
                delay_s = min(delay_s * 2, 8.0)

        raise RuntimeError("unreachable")  # pragma: no cover

    async def stream(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式输出。

        产出事件：
        - {"type": "text", "text": "..."}  # 增量文本
        - {"type": "final", "response": LLMResponse(...)}  # 最终聚合（包含 tool_calls）
        """
        print(f"[DoubaoLLMService] 开始流式生成请求，model={model or self.settings.doubao_llm_model}, max_tokens={max_tokens}")
        client = self._get_client()

        payload: dict[str, Any] = {
            "model": model or self.settings.doubao_llm_model,
            "max_tokens": max_tokens,
            "messages": messages,
            "stream": True,
            "thinking": {"type": "disabled"},
            **kwargs,
        }
        
        if system is not None:
            payload["messages"].insert(0, {"role": "system", "content": system})
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature

        print(f"[DoubaoLLMService] 流式请求参数：messages={len(messages)}, system={bool(system)}, tools={bool(tools)}")
        delay_s = 0.5
        for attempt in range(self.max_retries + 1):
            try:
                print(f"[DoubaoLLMService] 第 {attempt + 1} 次尝试发送流式请求")
                async with client.stream(
                    "POST",
                    self.settings.doubao_llm_endpoint,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    
                    full_text = ""
                    tool_calls_buffer: list[dict[str, Any]] = []
                    
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        
                        choices = data.get("choices", [])
                        if not choices:
                            continue
                        
                        delta = choices[0].get("delta", {})
                        
                        if "content" in delta:
                            content = delta["content"]
                            if isinstance(content, str) and content:
                                full_text += content
                                yield {"type": "text", "text": content}
                        
                        if "tool_calls" in delta:
                            tool_calls_buffer.extend(delta["tool_calls"])
                    
                    final_response = LLMResponse(
                        text=full_text,
                        tool_calls=self._parse_tool_calls(tool_calls_buffer),
                        raw={"text": full_text, "tool_calls": tool_calls_buffer},
                    )
                    print(f"[DoubaoLLMService] 流式请求成功，最终文本长度: {len(full_text)}")
                    yield {"type": "final", "response": final_response}
                return
            except Exception as exc:
                print(f"[DoubaoLLMService] 流式请求失败: {type(exc).__name__}: {exc}")
                if attempt >= self.max_retries or not self._is_retryable_error(exc):
                    raise
                print(f"[DoubaoLLMService] 等待 {delay_s} 秒后重试")
                await asyncio.sleep(delay_s)
                delay_s = min(delay_s * 2, 8.0)

        raise RuntimeError("unreachable")  # pragma: no cover


def create_llm_service(settings: Settings, *, max_retries: int = 3) -> LLMService | DoubaoLLMService:
    """根据配置创建 LLM 服务实例"""
    if settings.llm_provider == "doubao":
        return DoubaoLLMService(settings, max_retries=max_retries)
    return LLMService(settings, max_retries=max_retries)
