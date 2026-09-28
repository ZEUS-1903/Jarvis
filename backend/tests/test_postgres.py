"""Tests against a real PostgreSQL. Skipped if none is reachable.

Uses a separate database so tests never touch your real data:
    createdb jarvis_test
    (override with JARVIS_TEST_DATABASE_URL)
"""
import os

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.conversation.store import ConversationNotFound, PostgresConversationStore
from app.db.database import make_pool, migrate, open_pool
from app.llm.base import Message
from app.memory.store import MemoryNotFound, PostgresMemoryStore
from tests.fakes import FakeLLM, text

TEST_DB = os.environ.get("JARVIS_TEST_DATABASE_URL", "postgresql://localhost:5432/jarvis_test")


def _db_available() -> bool:
    try:
        psycopg.connect(TEST_DB, connect_timeout=2).close()
        return True
    except psycopg.Error:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason=f"no PostgreSQL at {TEST_DB}")


@pytest.fixture
async def pool():
    pool = make_pool(TEST_DB)
    await open_pool(pool, TEST_DB)
    async with pool.connection() as conn:  # clean slate for every test
        await conn.execute("DROP TABLE IF EXISTS messages, conversations, memories, schema_migrations")
    await migrate(pool)
    yield pool
    await pool.close()


async def test_migrations_apply_once(pool):
    assert await migrate(pool) == []  # already applied by the fixture


async def test_conversation_roundtrip_and_bound(pool):
    store = PostgresConversationStore(pool, max_messages=3)
    cid = await store.create()
    await store.append(cid, Message(role="user", content="one"), Message(role="assistant", content="two"))
    await store.append(cid, Message(role="user", content="it's O'Brien; DROP TABLE messages;--"))
    await store.append(cid, Message(role="assistant", content="four"))
    got = await store.get(cid)
    assert [m.content for m in got] == ["two", "it's O'Brien; DROP TABLE messages;--", "four"]
    with pytest.raises(ConversationNotFound):
        await store.get("c_missing")


async def test_memory_store_crud(pool):
    store = PostgresMemoryStore(pool)
    a = await store.add("Prefers tea", "preference", "active", "user")
    p = await store.add("Likes jazz", "preference", "pending", "assistant")
    assert [m.content for m in await store.list("active")] == ["Prefers tea"]
    assert (await store.approve(p.id)).status == "active"
    await store.delete(a.id)
    assert [m.id for m in await store.list()] == [p.id]
    with pytest.raises(MemoryNotFound):
        await store.delete(a.id)
    with pytest.raises(MemoryNotFound):
        await store.approve(12345)


async def test_database_rejects_invalid_category(pool):
    store = PostgresMemoryStore(pool)
    with pytest.raises(psycopg.errors.CheckViolation):
        await store.add("x", "nonsense", "active", "user")  # type: ignore[arg-type]


def test_full_app_persists_across_restart(monkeypatch):
    """Start the real app on Postgres, chat, 'restart', and the conversation is still there."""
    from app.config import get_settings
    from app.main import create_app

    with psycopg.connect(TEST_DB) as conn:
        conn.execute("DROP TABLE IF EXISTS messages, conversations, memories, schema_migrations")
    monkeypatch.setenv("JARVIS_DATABASE_URL", TEST_DB)
    get_settings.cache_clear()
    try:
        with TestClient(create_app(llm=FakeLLM(text("Hi Sam.")))) as client:  # `with` runs startup
            cid = client.post("/api/chat", json={"message": "I'm Sam"}).json()["conversation_id"]
            client.post("/api/memories", json={"content": "Name is Sam", "category": "fact"})
        with TestClient(create_app(llm=FakeLLM())) as client:  # a fresh app = a restart
            msgs = client.get(f"/api/conversations/{cid}/messages").json()["messages"]
            mems = client.get("/api/memories").json()["active"]
        assert [m["content"] for m in msgs] == ["I'm Sam", "Hi Sam."]
        assert [m["content"] for m in mems] == ["Name is Sam"]
    finally:
        get_settings.cache_clear()
