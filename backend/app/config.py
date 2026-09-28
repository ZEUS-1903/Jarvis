"""Application settings, loaded from environment variables / .env.

Every setting lives here so the rest of the code never reads os.environ directly.
If a value is invalid, the app refuses to start (fail fast) instead of failing
later in the middle of a user request.
"""
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_prefix: JARVIS_LOG_LEVEL in the environment maps to `log_level` here.
    model_config = SettingsConfigDict(env_file=".env", env_prefix="JARVIS_", extra="ignore")

    log_level: str = "INFO"
    # Used when the user asks "what time is it?" without naming a place.
    default_timezone: str = "America/New_York"
    default_units: Literal["metric", "imperial"] = "imperial"
    # Used for "what's the weather?" with no place named. Empty = ask the user.
    default_location: str = ""

    # LLM: any server speaking the OpenAI-compatible Chat Completions API.
    # Default = Ollama running locally (free, private, no key).
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen3:8b"
    llm_api_key: SecretStr | None = None  # SecretStr: never printed in logs/reprs
    llm_timeout_s: float = 120.0          # local models on a laptop can be slow

    # Agent safety limits
    agent_max_iterations: int = 5         # max LLM<->tool rounds per user message
    history_max_messages: int = 20        # user+assistant messages kept per conversation

    @field_validator("default_timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown IANA timezone: {value!r}") from exc
        return value


@lru_cache
def get_settings() -> Settings:
    """Build settings once and reuse them (also easy to override in tests)."""
    return Settings()
