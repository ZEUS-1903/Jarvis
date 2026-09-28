"""HTTP request/response shapes for /api/chat (the frontend mirrors these in types.ts)."""
from pydantic import BaseModel, Field

from app.agent.loop import ToolTrace
from app.llm.base import Usage


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    # True when the message was spoken: the reply will be read aloud, so the
    # agent is told to keep it short and speakable.
    voice: bool = False


class ChatUsage(Usage):
    llm_calls: int


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    tool_calls: list[ToolTrace]
    usage: ChatUsage
    request_id: str | None
