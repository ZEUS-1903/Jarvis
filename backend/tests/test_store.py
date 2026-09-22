import pytest

from app.conversation.store import ConversationNotFound, InMemoryConversationStore
from app.llm.base import Message


def test_history_is_trimmed_to_most_recent():
    store = InMemoryConversationStore(max_messages=4)
    cid = store.create()
    for i in range(6):
        store.append(cid, Message(role="user", content=str(i)))
    assert [m.content for m in store.get(cid)] == ["2", "3", "4", "5"]


def test_unknown_conversation():
    with pytest.raises(ConversationNotFound):
        InMemoryConversationStore().get("c_missing")
