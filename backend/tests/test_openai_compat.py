"""Adapter tests: exact wire format in both directions, retries, failures."""
import json

import httpx
import pytest

from app.llm.base import LLMError, Message, ToolCall
from app.llm.openai_compat import OpenAICompatClient


def client_with(handler, **kw):
    return OpenAICompatClient("http://llm.test/v1", "test-model",
                              http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
                              **kw)


def ok(message, usage=None):
    return httpx.Response(200, json={"choices": [{"message": message}],
                                     "usage": usage or {"prompt_tokens": 7, "completion_tokens": 3}})


async def test_request_payload_shape():
    sent = {}

    def handler(request):
        sent.update(json.loads(request.content))
        sent["url"] = str(request.url)
        return ok({"role": "assistant", "content": "hi"})

    messages = [
        Message(role="user", content="2+2?"),
        Message(role="assistant", tool_calls=[ToolCall(id="c1", name="calculate",
                                                       arguments='{"expression":"2+2"}')]),
        Message(role="tool", tool_call_id="c1", content='{"result": 4}'),
    ]
    await client_with(handler).complete(messages, [{"name": "calculate", "description": "d",
                                                    "parameters": {"type": "object"}}])
    assert sent["url"] == "http://llm.test/v1/chat/completions"
    assert sent["model"] == "test-model"
    assert sent["tools"][0] == {"type": "function", "function": {
        "name": "calculate", "description": "d", "parameters": {"type": "object"}}}
    assert sent["messages"][1]["tool_calls"][0]["function"]["arguments"] == '{"expression":"2+2"}'
    assert sent["messages"][2]["tool_call_id"] == "c1"


async def test_parses_tool_calls_and_usage():
    resp = await client_with(lambda r: ok({"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_9", "type": "function",
         "function": {"name": "get_weather", "arguments": '{"location": "Boston"}'}},
    ]})).complete([Message(role="user", content="weather?")], [])
    assert resp.text is None
    assert resp.tool_calls == [ToolCall(id="call_9", name="get_weather",
                                        arguments='{"location": "Boston"}')]
    assert resp.usage.input_tokens == 7


async def test_object_arguments_and_missing_id_are_normalized():
    resp = await client_with(lambda r: ok({"role": "assistant", "tool_calls": [
        {"function": {"name": "calculate", "arguments": {"expression": "1+1"}}},
    ]})).complete([], [])
    assert json.loads(resp.tool_calls[0].arguments) == {"expression": "1+1"}
    assert resp.tool_calls[0].id.startswith("call_")


async def test_think_tags_are_stripped():
    resp = await client_with(lambda r: ok({"role": "assistant",
                                           "content": "<think>internal</think>\n\nIt's 4."})
                             ).complete([], [])
    assert resp.text == "It's 4."


async def test_retries_503_then_succeeds(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    attempts = []

    def handler(request):
        attempts.append(1)
        return httpx.Response(503) if len(attempts) < 2 else ok({"content": "ok"})

    resp = await client_with(handler).complete([], [])
    assert resp.text == "ok" and len(attempts) == 2


async def test_404_model_not_found_fails_without_retry():
    attempts = []

    def handler(request):
        attempts.append(1)
        return httpx.Response(404, json={"error": "model 'x' not found"})

    with pytest.raises(LLMError, match="404"):
        await client_with(handler).complete([], [])
    assert len(attempts) == 1


async def test_connection_refused(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)

    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(LLMError, match="cannot reach"):
        await client_with(handler).complete([], [])


async def _no_sleep(_):
    return None
