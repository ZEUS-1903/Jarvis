import json

from app.agent.loop import STEP_LIMIT_REPLY, Agent
from app.tools import build_default_registry
from tests.fakes import FakeLLM, calls, text


def make_agent(llm, max_iterations=5):
    return Agent(llm, build_default_registry(), timezone="America/New_York",
                 units="imperial", max_iterations=max_iterations)


async def test_no_tools_needed():
    llm = FakeLLM(text("Hello!"))
    result = await make_agent(llm).run([], "hi")
    assert result.reply == "Hello!" and result.llm_calls == 1 and result.tool_calls == []
    assert [m.role for m in llm.calls[0]] == ["system", "user"]


async def test_tool_round_trip():
    llm = FakeLLM(calls(("calculate", '{"expression": "6*7"}')), text("It's 42."))
    result = await make_agent(llm).run([], "what is 6 times 7")

    assert result.reply == "It's 42." and result.llm_calls == 2
    assert result.tool_calls[0].name == "calculate" and result.tool_calls[0].ok
    assert result.usage.input_tokens == 20

    # Second LLM call must contain: the assistant's tool request, then the result
    # linked by the same id.
    second = llm.calls[1]
    assert [m.role for m in second] == ["system", "user", "assistant", "tool"]
    assert second[2].tool_calls[0].id == "call_0"
    assert second[3].tool_call_id == "call_0"
    assert json.loads(second[3].content)["result"] == 42


async def test_parallel_tool_calls_keep_order():
    llm = FakeLLM(
        calls(("get_current_time", '{"timezone": "Asia/Tokyo"}'),
              ("calculate", '{"expression": "1+1"}')),
        text("done"),
    )
    result = await make_agent(llm).run([], "time in Tokyo and 1+1")
    assert [t.name for t in result.tool_calls] == ["get_current_time", "calculate"]
    tool_msgs = [m for m in llm.calls[1] if m.role == "tool"]
    assert [m.tool_call_id for m in tool_msgs] == ["call_0", "call_1"]


async def test_tool_error_goes_back_to_model_not_to_user_as_crash():
    llm = FakeLLM(calls(("does_not_exist", "{}")), text("Sorry, I can't do that."))
    result = await make_agent(llm).run([], "do the impossible")
    assert result.tool_calls[0].ok is False
    assert "unknown tool" in json.loads(llm.calls[1][-1].content)["error"]
    assert result.reply == "Sorry, I can't do that."


async def test_step_limit_stops_runaway_loop():
    llm = FakeLLM(*[calls(("calculate", '{"expression": "1"}'))] * 3)
    result = await make_agent(llm, max_iterations=3).run([], "loop forever")
    assert result.reply == STEP_LIMIT_REPLY and result.llm_calls == 3


async def test_history_is_included():
    from app.llm.base import Message
    llm = FakeLLM(text("Your name is Sam."))
    history = [Message(role="user", content="I'm Sam"), Message(role="assistant", content="Hi Sam")]
    await make_agent(llm).run(history, "what's my name?")
    assert [m.content for m in llm.calls[0][1:]] == ["I'm Sam", "Hi Sam", "what's my name?"]


async def test_home_location_in_system_prompt():
    llm = FakeLLM(text("ok"))
    agent = Agent(llm, build_default_registry(), timezone="America/New_York",
                  units="imperial", location="Boston")
    await agent.run([], "weather?")
    assert "home location: Boston" in llm.calls[0][0].content


async def test_unknown_location_tells_model_to_ask():
    llm = FakeLLM(text("ok"))
    await make_agent(llm).run([], "weather?")
    assert "unknown; ask" in llm.calls[0][0].content
