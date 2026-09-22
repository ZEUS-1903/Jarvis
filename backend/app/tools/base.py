"""The contract every JARVIS tool follows.

A tool is a small class declaring:
  - name / description  -> what the LLM reads when deciding which tool to use
  - input_model         -> a Pydantic model: validates arguments AND generates the
                           JSON Schema we send to the LLM (one source of truth)
  - permission          -> risk level; the registry enforces it
  - timeout_s           -> hard limit on execution time
  - run()               -> the actual logic; returns plain JSON-serializable data
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel


class Permission(str, Enum):
    LOW = "low"        # read-only, public data: runs automatically
    MEDIUM = "medium"  # reads personal data: needs authenticated access (Phase 4)
    HIGH = "high"      # changes the world: needs explicit user confirmation (Phase 4)


class ToolError(Exception):
    """An *expected* failure whose message is safe to show the LLM/user,
    e.g. "unknown timezone" or "division by zero". Anything else is treated
    as an internal bug and reported generically."""


class ToolResult(BaseModel):
    name: str
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: float = 0.0

    def for_llm(self) -> dict[str, Any]:
        """What the model sees: the data, or an error it can explain to the user."""
        return self.data if self.ok else {"error": self.error}


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    input_model: ClassVar[type[BaseModel]]
    permission: ClassVar[Permission] = Permission.LOW
    timeout_s: ClassVar[float] = 10.0

    @abstractmethod
    async def run(self, args: BaseModel) -> dict[str, Any]:
        """Execute with already-validated args. Raise ToolError for expected failures."""

    def schema(self) -> dict[str, Any]:
        """Provider-neutral tool definition; the LLM adapter wraps it as needed."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_model.model_json_schema(),
        }
