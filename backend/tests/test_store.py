import pytest

from app.conversation.store import ConversationNotFound, InMemoryConversationStore
from app.llm.base import Message


async def test_history_is_bounded_to_most_recent():
    store = InMemoryConversationStore(max_messages=4)
    cid = await store.create()
    for i in range(6):
        await store.append(cid, Message(role="user", content=str(i)))
    assert [m.content for m in await store.get(cid)] == ["2", "3", "4", "5"]


async def test_unknown_conversation():
    with pytest.raises(ConversationNotFound):
        await InMemoryConversationStore().get("c_missing")
