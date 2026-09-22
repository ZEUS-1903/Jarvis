"""Provider-neutral message types and the LLMClient interface.

The agent only ever speaks this format. Each provider adapter translates it to
and from the provider's wire format, so switching providers touches one file.
"""
from typing import Any, Literal, Protocol

from pydantic import BaseModel


class ToolCall(BaseModel):
    id: str          # links a tool result back to the call that requested it
    name: str
    arguments: str   # raw JSON string exactly as the model produced it (unvalidated!)


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] = []   # assistant messages only
    tool_call_id: str | None = None   # tool messages only


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class LLMResponse(BaseModel):
    text: str | None
    tool_calls: list[ToolCall]
    usage: Usage


class LLMError(Exception):
    """The model provider could not be reached or returned garbage."""


class LLMClient(Protocol):
    model: str

    async def complete(
        self, messages: list[Message], tools: list[dict[str, Any]]
    ) -> LLMResponse: ...
