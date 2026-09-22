"""Conversation history, keyed by conversation_id.

V1 keeps it in a Python dict: zero setup, but everything is lost on restart and
it only works with a single server process. Phase 2 swaps in Postgres behind the
same methods, so the agent and API code won't change.
"""
import uuid

from app.llm.base import Message


class ConversationNotFound(Exception):
    pass


class InMemoryConversationStore:
    def __init__(self, max_messages: int = 20) -> None:
        self._conversations: dict[str, list[Message]] = {}
        self._max_messages = max_messages

    def create(self) -> str:
        conversation_id = f"c_{uuid.uuid4().hex[:12]}"
        self._conversations[conversation_id] = []
        return conversation_id

    def get(self, conversation_id: str) -> list[Message]:
        if conversation_id not in self._conversations:
            raise ConversationNotFound(conversation_id)
        return list(self._conversations[conversation_id])  # copy: callers can't mutate ours

    def append(self, conversation_id: str, *messages: Message) -> None:
        history = self._conversations[conversation_id]
        history.extend(messages)
        # Keep only the most recent messages so the prompt can't grow forever.
        # (Crude but predictable; later phases summarize instead of dropping.)
        del history[: max(0, len(history) - self._max_messages)]
