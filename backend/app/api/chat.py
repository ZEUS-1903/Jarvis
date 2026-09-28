import logging
import time

from fastapi import APIRouter, HTTPException, Request

from app.agent.prompts import PROMPT_VERSION
from app.conversation.store import ConversationNotFound
from app.llm.base import LLMError, Message
from app.observability.logging import request_id_var
from app.schemas.chat import ChatRequest, ChatResponse, ChatUsage

router = APIRouter()
logger = logging.getLogger("jarvis.chat")


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    # Shared objects created once at startup (see main.py) live on app.state.
    store = request.app.state.store
    agent = request.app.state.agent
    start = time.perf_counter()

    conversation_id = body.conversation_id
    history: list[Message] = []
    if conversation_id is not None:
        try:
            history = await store.get(conversation_id)
        except ConversationNotFound:
            raise HTTPException(404, "conversation not found; start a new one")

    logger.info("chat.request", extra={"conversation_id": conversation_id,
                                       "message_chars": len(body.message),
                                       "voice": body.voice})
    try:
        result = await agent.run(history, body.message, voice=body.voice)
    except LLMError as exc:
        logger.error("chat.llm_error", extra={"conversation_id": conversation_id,
                                              "error": str(exc)})
        raise HTTPException(502, f"The language model is unavailable: {exc}")

    if conversation_id is None:
        conversation_id = await store.create()  # only once we have something to save
    # Store only user text + final reply (not tool traffic) to keep context small.
    await store.append(conversation_id,
                 Message(role="user", content=body.message),
                 Message(role="assistant", content=result.reply))

    logger.info("chat.response", extra={
        "conversation_id": conversation_id,
        "model": agent.llm.model,
        "prompt_version": PROMPT_VERSION,
        "llm_calls": result.llm_calls,
        "tools": [t.name for t in result.tool_calls],
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "latency_ms": round((time.perf_counter() - start) * 1000, 1),
    })
    return ChatResponse(
        conversation_id=conversation_id,
        reply=result.reply,
        tool_calls=result.tool_calls,
        usage=ChatUsage(**result.usage.model_dump(), llm_calls=result.llm_calls),
        request_id=request_id_var.get(),
    )


@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id: str, request: Request) -> dict:
    """Recent messages, so the UI can restore a conversation after a page reload."""
    try:
        history = await request.app.state.store.get(conversation_id)
    except ConversationNotFound:
        raise HTTPException(404, "conversation not found")
    return {"messages": [{"role": m.role, "content": m.content} for m in history]}
