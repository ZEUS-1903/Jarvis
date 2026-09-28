"""Conversation history, keyed by conversation_id.

Two implementations of the same async interface:
  - PostgresConversationStore: the real one; survives restarts.
  - InMemoryConversationStore: for tests (no database needed).
"""
import uuid
from typing import Protocol

from psycopg_pool import AsyncConnectionPool

from app.llm.base import Message


class ConversationNotFound(Exception):
    pass


class ConversationStore(Protocol):
    async def create(self) -> str: ...
    async def get(self, conversation_id: str) -> list[Message]:
        """The most recent messages (bounded), oldest first."""
        ...
    async def append(self, conversation_id: str, *messages: Message) -> None: ...


def new_conversation_id() -> str:
    return f"c_{uuid.uuid4().hex[:12]}"


class PostgresConversationStore:
    def __init__(self, pool: AsyncConnectionPool, max_messages: int = 20) -> None:
        self._pool = pool
        self._max = max_messages

    async def create(self) -> str:
        cid = new_conversation_id()
        async with self._pool.connection() as conn:
            await conn.execute("INSERT INTO conversations (id) VALUES (%s)", (cid,))
        return cid

    async def get(self, conversation_id: str) -> list[Message]:
        async with self._pool.connection() as conn:
            exists = await (await conn.execute(
                "SELECT 1 FROM conversations WHERE id = %s", (conversation_id,))).fetchone()
            if not exists:
                raise ConversationNotFound(conversation_id)
            # Newest N first (uses the index), then flip to chronological order.
            # Everything is stored; only what we *send to the model* is bounded.
            rows = await (await conn.execute(
                "SELECT role, content FROM messages WHERE conversation_id = %s "
                "ORDER BY id DESC LIMIT %s", (conversation_id, self._max))).fetchall()
        return [Message(role=role, content=content) for role, content in reversed(rows)]

    async def append(self, conversation_id: str, *messages: Message) -> None:
        async with self._pool.connection() as conn:
            # One transaction: a user message is never saved without its reply.
            async with conn.transaction():
                for m in messages:
                    # %s placeholders: psycopg sends values separately from the SQL
                    # text, so message content can never be executed as SQL.
                    await conn.execute(
                        "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)",
                        (conversation_id, m.role, m.content))


class InMemoryConversationStore:
    def __init__(self, max_messages: int = 20) -> None:
        self._conversations: dict[str, list[Message]] = {}
        self._max = max_messages

    async def create(self) -> str:
        cid = new_conversation_id()
        self._conversations[cid] = []
        return cid

    async def get(self, conversation_id: str) -> list[Message]:
        if conversation_id not in self._conversations:
            raise ConversationNotFound(conversation_id)
        return list(self._conversations[conversation_id][-self._max:])

    async def append(self, conversation_id: str, *messages: Message) -> None:
        self._conversations[conversation_id].extend(messages)
