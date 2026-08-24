"""LLM 客户端：OpenAI 兼容抽象，供 agents / graph 调用。

统一入口 get_client()，懒加载（未配置 key 时模块可正常 import，仅在调用时报错）。
提供：同步/异步补全、JSON 结构化输出、流式（后续 chat SSE 用）。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

from openai import AsyncOpenAI, OpenAI

from .config import get_settings

_JSON_RESPONSE_FORMAT = {"type": "json_object"}
_JSON_RETRY_HINT = (
    "你上次的输出被截断或不是合法 JSON。请重新输出一个完整、合法、自闭合的 JSON 对象，"
    "不要省略任何字段，不要在 JSON 外添加文字。"
)


class LLMError(RuntimeError):
    """LLM 调用失败（重试后仍失败）。"""


class LLMClient:
    def __init__(self, json_retries: int = 2) -> None:
        s = get_settings()
        if not s.is_configured:
            raise LLMError(
                f"LLM({s.provider}) 未配置 API Key：请在 backend/.env 设置 "
                f"{s.provider.upper()}_API_KEY"
            )
        common = dict(base_url=s.base_url, api_key=s.api_key, timeout=s.timeout, max_retries=2)
        self._sync = OpenAI(**common)
        self._async = AsyncOpenAI(**common)
        self.settings = s
        self._json_retries = json_retries

    # ---- 内部工具 ----
    def _messages(self, system: str | None, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        return ([{"role": "system", "content": system}] if system else []) + messages

    def _params(self, temperature: float | None, max_tokens: int | None) -> dict[str, Any]:
        return {
            "temperature": self.settings.temperature if temperature is None else temperature,
            "max_tokens": self.settings.max_tokens if max_tokens is None else max_tokens,
        }

    # ---- 同步 ----
    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        resp = self._sync.chat.completions.create(
            model=self.settings.model,
            messages=self._messages(system, messages),
            **self._params(temperature, max_tokens),
        )
        return (resp.choices[0].message.content or "").strip()

    def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        raw = ""
        msgs = self._messages(system, messages)
        for attempt in range(self._json_retries + 1):
            resp = self._sync.chat.completions.create(
                model=self.settings.model,
                messages=msgs,
                response_format=_JSON_RESPONSE_FORMAT,
                **self._params(temperature, max_tokens),
            )
            raw = resp.choices[0].message.content or ""
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                if attempt < self._json_retries:
                    # 廉价模型偶发截断：带修正提示重试
                    msgs = msgs + [{"role": "system", "content": _JSON_RETRY_HINT}]
        raise LLMError(f"LLM 返回内容不是合法 JSON: {raw[:200]}")

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        stream = self._sync.chat.completions.create(
            model=self.settings.model,
            messages=self._messages(system, messages),
            stream=True,
            **self._params(temperature, max_tokens),
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    # ---- 异步 ----
    async def acomplete(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        resp = await self._async.chat.completions.create(
            model=self.settings.model,
            messages=self._messages(system, messages),
            **self._params(temperature, max_tokens),
        )
        return (resp.choices[0].message.content or "").strip()

    async def acomplete_json(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        raw = ""
        msgs = self._messages(system, messages)
        for attempt in range(self._json_retries + 1):
            resp = await self._async.chat.completions.create(
                model=self.settings.model,
                messages=msgs,
                response_format=_JSON_RESPONSE_FORMAT,
                **self._params(temperature, max_tokens),
            )
            raw = resp.choices[0].message.content or ""
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                if attempt < self._json_retries:
                    msgs = msgs + [{"role": "system", "content": _JSON_RETRY_HINT}]
        raise LLMError(f"LLM 返回内容不是合法 JSON: {raw[:200]}")

    async def astream(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        stream = await self._async.chat.completions.create(
            model=self.settings.model,
            messages=self._messages(system, messages),
            stream=True,
            **self._params(temperature, max_tokens),
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content


_client: LLMClient | None = None


def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
