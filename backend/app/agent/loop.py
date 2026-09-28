"""The agent loop: LLM -> (tools -> LLM)* -> answer.

This is the heart of JARVIS V1:

    messages = system + history + user
    repeat up to max_iterations:
        response = LLM(messages, tool schemas)
        if no tool calls: done, response.text is the answer
        append the assistant's tool-call message
        execute every requested tool (concurrently) via the registry
        append one "tool" message per result, linked by tool_call_id
"""
import asyncio
import json
import logging

from pydantic import BaseModel

from app.agent.prompts import build_system_prompt
from app.llm.base import LLMClient, Message, Usage
from app.tools.registry import ToolRegistry

logger = logging.getLogger("jarvis.agent")

STEP_LIMIT_REPLY = (
    "I couldn't finish that within my step limit. Could you break it into smaller requests?"
)
EMPTY_REPLY = "Sorry, I didn't manage to produce an answer. Could you rephrase that?"


class ToolTrace(BaseModel):
    name: str
    arguments: str
    ok: bool
    error: str | None
    duration_ms: float


class AgentResult(BaseModel):
    reply: str
    tool_calls: list[ToolTrace]
    usage: Usage
    llm_calls: int


class Agent:
    def __init__(
        self, llm: LLMClient, tools: ToolRegistry, *, timezone: str, units: str,
        location: str = "", max_iterations: int = 5,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.timezone = timezone
        self.units = units
        self.location = location
        self.max_iterations = max_iterations

    async def run(self, history: list[Message], user_text: str, voice: bool = False) -> AgentResult:
        system = build_system_prompt(self.timezone, self.units, self.location, voice=voice)
        messages = [
            Message(role="system", content=system),
            *history,
            Message(role="user", content=user_text),
        ]
        schemas = self.tools.schemas()
        traces: list[ToolTrace] = []
        usage = Usage()

        for iteration in range(1, self.max_iterations + 1):
            response = await self.llm.complete(messages, schemas)
            usage.input_tokens += response.usage.input_tokens
            usage.output_tokens += response.usage.output_tokens

            if not response.tool_calls:
                return AgentResult(reply=response.text or EMPTY_REPLY, tool_calls=traces,
                                   usage=usage, llm_calls=iteration)

            # The assistant's tool request must stay in the transcript: the next
            # LLM call needs to see what it asked for to interpret the results.
            messages.append(Message(role="assistant", content=response.text,
                                    tool_calls=response.tool_calls))

            # Independent tool calls run concurrently; gather keeps input order.
            results = await asyncio.gather(
                *(self.tools.execute(tc.name, tc.arguments) for tc in response.tool_calls)
            )
            for call, result in zip(response.tool_calls, results):
                messages.append(Message(
                    role="tool",
                    tool_call_id=call.id,
                    content=json.dumps(result.for_llm(), ensure_ascii=False),
                ))
                traces.append(ToolTrace(name=call.name, arguments=call.arguments, ok=result.ok,
                                        error=result.error, duration_ms=result.duration_ms))

        logger.warning("agent.step_limit", extra={"max_iterations": self.max_iterations})
        return AgentResult(reply=STEP_LIMIT_REPLY, tool_calls=traces, usage=usage,
                           llm_calls=self.max_iterations)
