"""The registry is the security boundary between the LLM and code execution."""
import asyncio
from typing import ClassVar

from pydantic import BaseModel

from app.tools import Permission, Tool, ToolRegistry, build_default_registry


class NoArgs(BaseModel):
    pass


class SlowTool(Tool):
    name = "slow"
    description = "sleeps"
    input_model = NoArgs
    timeout_s = 0.05

    async def run(self, args):
        await asyncio.sleep(1)
        return {}


class BuggyTool(Tool):
    name = "buggy"
    description = "crashes"
    input_model = NoArgs

    async def run(self, args):
        raise RuntimeError("secret internal detail")


class SendEmailTool(Tool):
    name = "send_email"
    description = "high risk"
    input_model = NoArgs
    permission: ClassVar[Permission] = Permission.HIGH
    ran = False

    async def run(self, args):
        SendEmailTool.ran = True
        return {}


registry = build_default_registry()


async def test_schemas_exposed_to_llm():
    names = {s["name"] for s in registry.schemas()}
    assert names == {"get_current_time", "calculate", "get_weather"}
    calc = next(s for s in registry.schemas() if s["name"] == "calculate")
    assert calc["parameters"]["required"] == ["expression"]


async def test_success_with_json_string_args():
    result = await registry.execute("calculate", '{"expression": "6 * 7"}')
    assert result.ok and result.data["result"] == 42
    assert result.for_llm() == {"expression": "6 * 7", "result": 42}


async def test_unknown_tool_is_refused():
    result = await registry.execute("delete_everything", {})
    assert not result.ok and "unknown tool" in result.error


async def test_malformed_json_args():
    result = await registry.execute("calculate", "{not json")
    assert not result.ok and "not valid JSON" in result.error


async def test_schema_violation_names_the_field():
    result = await registry.execute("calculate", {"expr": "1+1"})
    assert not result.ok and "expression" in result.error


async def test_expected_tool_error_is_passed_through():
    result = await registry.execute("calculate", {"expression": "1/0"})
    assert result.for_llm() == {"error": "division by zero"}


async def test_timeout():
    result = await ToolRegistry([SlowTool()]).execute("slow", {})
    assert not result.ok and "timed out" in result.error


async def test_crash_does_not_leak_internals():
    result = await ToolRegistry([BuggyTool()]).execute("buggy", {})
    assert not result.ok and "secret" not in result.error


async def test_high_risk_tool_never_runs_in_v1():
    result = await ToolRegistry([SendEmailTool()]).execute("send_email", {})
    assert not result.ok and "confirmation" in result.error
    assert SendEmailTool.ran is False


async def test_secret_arguments_are_redacted_in_logs(caplog):
    import logging
    caplog.set_level(logging.INFO, logger="jarvis.tools")
    await registry.execute("calculate", {"expression": "my password is hunter2"})
    logged = [r.tool_args for r in caplog.records if getattr(r, "tool", None) == "calculate"]
    assert logged == ["[redacted: looks like a secret]"]
    assert "hunter2" not in caplog.text
