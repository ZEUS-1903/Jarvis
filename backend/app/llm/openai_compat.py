"""Adapter for the OpenAI-compatible Chat Completions API.

Spoken by OpenAI itself and by many others (Ollama, Groq, Google Gemini's
compatibility endpoint, vLLM, LM Studio...). We call it with plain httpx instead
of an SDK so every byte of the protocol is visible:

POST {base_url}/chat/completions
{
  "model": "qwen3:8b",
  "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
  "tools": [{"type": "function", "function": {"name": ..., "description": ..., "parameters": {JSON Schema}}}]
}
-> {"choices": [{"message": {"role": "assistant", "content": "...", "tool_calls": [
       {"id": "call_1", "type": "function", "function": {"name": "...", "arguments": "{json string}"}}]}}],
    "usage": {"prompt_tokens": 520, "completion_tokens": 48}}
"""
import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any

import httpx

from app.llm.base import LLMError, LLMResponse, Message, ToolCall, Usage

logger = logging.getLogger("jarvis.llm")

# Reasoning models (e.g. Qwen3) may emit hidden reasoning inside <think> tags.
# It is not meant for the user, so we strip it.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class OpenAICompatClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_s: float = 120.0,
        max_retries: int = 2,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._max_retries = max_retries
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = http_client or httpx.AsyncClient(timeout=timeout_s, headers=headers)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_to_wire(m) for m in messages],
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]

        start = time.perf_counter()
        body = await self._post_with_retries(payload)
        response = _from_wire(body)
        logger.info(
            "llm.call",
            extra={
                "model": self.model,
                "messages": len(messages),
                "tool_calls": [tc.name for tc in response.tool_calls],
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        return response

    async def _post_with_retries(self, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.post(self._url, json=payload)
            except httpx.TimeoutException as exc:
                # Don't retry timeouts: a slow local model will just be slow again.
                raise LLMError("LLM request timed out") from exc
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    raise LLMError(f"cannot reach LLM at {self._url}") from exc
            else:
                if resp.status_code < 400:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        raise LLMError("LLM returned non-JSON response") from exc
                if resp.status_code not in _RETRYABLE_STATUS or attempt == self._max_retries:
                    # 4xx such as a wrong model name is a config error: fail now.
                    raise LLMError(f"LLM returned HTTP {resp.status_code}: {resp.text[:300]}")
            await asyncio.sleep(0.5 * 2**attempt)  # 0.5s, 1s, ... exponential backoff
        raise AssertionError("unreachable")


def _to_wire(m: Message) -> dict[str, Any]:
    wire: dict[str, Any] = {"role": m.role, "content": m.content or ""}
    if m.tool_calls:
        wire["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.name, "arguments": tc.arguments}}
            for tc in m.tool_calls
        ]
    if m.tool_call_id:
        wire["tool_call_id"] = m.tool_call_id
    return wire


def _from_wire(body: dict[str, Any]) -> LLMResponse:
    try:
        message = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("LLM response missing choices[0].message") from exc

    tool_calls = []
    for raw in message.get("tool_calls") or []:
        fn = raw.get("function") or {}
        args = fn.get("arguments", "")
        tool_calls.append(ToolCall(
            # Some servers omit ids; we need one to pair results with calls.
            id=raw.get("id") or f"call_{uuid.uuid4().hex[:8]}",
            name=fn.get("name", ""),
            # Spec says a JSON string, but some servers send an object.
            arguments=args if isinstance(args, str) else json.dumps(args),
        ))

    text = message.get("content")
    if text:
        text = _THINK_RE.sub("", text).strip() or None

    usage = body.get("usage") or {}
    return LLMResponse(
        text=text,
        tool_calls=tool_calls,
        usage=Usage(input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0)),
    )
