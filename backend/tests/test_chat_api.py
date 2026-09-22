from fastapi.testclient import TestClient

from app.llm.base import LLMError
from app.main import create_app
from tests.fakes import FakeLLM, calls, text


def test_full_request_with_tool_call():
    llm = FakeLLM(calls(("calculate", '{"expression": "1200*0.15"}')), text("That's 180."))
    client = TestClient(create_app(llm=llm))

    r = client.post("/api/chat", json={"message": "15% of 1200?"})
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "That's 180."
    assert body["conversation_id"].startswith("c_")
    assert body["tool_calls"][0]["name"] == "calculate" and body["tool_calls"][0]["ok"]
    assert body["usage"]["llm_calls"] == 2
    assert body["request_id"] == r.headers["X-Request-ID"]


def test_conversation_history_carries_over():
    llm = FakeLLM(text("Nice to meet you, Sam."), text("You're Sam."))
    client = TestClient(create_app(llm=llm))
    cid = client.post("/api/chat", json={"message": "I'm Sam"}).json()["conversation_id"]
    client.post("/api/chat", json={"conversation_id": cid, "message": "Who am I?"})
    second_call = [m.content for m in llm.calls[1] if m.role != "system"]
    assert second_call == ["I'm Sam", "Nice to meet you, Sam.", "Who am I?"]


def test_unknown_conversation_is_404():
    client = TestClient(create_app(llm=FakeLLM()))
    r = client.post("/api/chat", json={"conversation_id": "c_nope", "message": "hi"})
    assert r.status_code == 404


def test_validation_errors_are_422():
    client = TestClient(create_app(llm=FakeLLM()))
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
    assert client.post("/api/chat", json={"message": "x" * 4001}).status_code == 422


def test_llm_down_is_502():
    client = TestClient(create_app(llm=FakeLLM(LLMError("cannot reach LLM"))))
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 502 and "unavailable" in r.json()["detail"]


def test_failed_request_creates_no_conversation():
    app = create_app(llm=FakeLLM(LLMError("down")))
    TestClient(app).post("/api/chat", json={"message": "hi"})
    assert app.state.store._conversations == {}
