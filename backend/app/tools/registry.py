"""The tool registry: the ONLY path from an LLM tool request to executed code.

The LLM proposes {"name": ..., "arguments": ...}. Before anything runs we check:
  1. the tool is registered (allow-list)          -> else error result
  2. its permission level is allowed right now     -> else error result
  3. the arguments parse and match the schema      -> else error result
Then we run it with a timeout. Every outcome becomes a ToolResult; nothing here
raises, so one bad tool call can never crash the whole chat request.
"""
import asyncio
import json
import logging
import time
from typing import Any

from pydantic import ValidationError

from app.security.secrets import redact
from app.tools.base import Permission, Tool, ToolError, ToolResult

logger = logging.getLogger("jarvis.tools")


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    async def execute(self, name: str, raw_args: dict[str, Any] | str | None) -> ToolResult:
        start = time.perf_counter()
        result = await self._execute(name, raw_args)
        result.duration_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "tool.executed",
            extra={
                "tool": name,
                # Never write secrets to logs (e.g. a refused "remember my password").
                "tool_args": redact(raw_args),
                "status": "ok" if result.ok else "error",
                "error": result.error,
                "duration_ms": result.duration_ms,
            },
        )
        return result

    async def _execute(self, name: str, raw_args: dict[str, Any] | str | None) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(name=name, ok=False, error=f"unknown tool '{name}'")

        # LOW (public data) and MEDIUM (reads your data; the tool itself needs
        # your Google authorization) run automatically. HIGH (changes things:
        # sending, deleting) is refused until the confirmation flow exists.
        if tool.permission is Permission.HIGH:
            return ToolResult(name=name, ok=False, error="tool requires user confirmation")

        # Providers usually send arguments as a JSON *string*; parse it here.
        if isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args) if raw_args.strip() else {}
            except json.JSONDecodeError:
                return ToolResult(name=name, ok=False, error="arguments are not valid JSON")
        try:
            args = tool.input_model.model_validate(raw_args or {})
        except ValidationError as exc:
            # Tell the model which fields were wrong so it can retry correctly.
            problems = "; ".join(
                f"{'.'.join(map(str, e['loc'])) or 'input'}: {e['msg']}" for e in exc.errors()
            )
            return ToolResult(name=name, ok=False, error=f"invalid arguments: {problems}")

        try:
            data = await asyncio.wait_for(tool.run(args), timeout=tool.timeout_s)
            return ToolResult(name=name, ok=True, data=data)
        except ToolError as exc:
            return ToolResult(name=name, ok=False, error=str(exc))
        except asyncio.TimeoutError:
            return ToolResult(name=name, ok=False, error=f"{name} timed out")
        except Exception:
            # A bug, not a user-facing condition: full traceback to logs,
            # generic message to the model (don't leak internals).
            logger.exception("tool.crashed", extra={"tool": name})
            return ToolResult(name=name, ok=False, error=f"{name} failed unexpectedly")
