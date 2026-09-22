"""Application settings, loaded from environment variables / .env.

Every setting lives here so the rest of the code never reads os.environ directly.
If a value is invalid, the app refuses to start (fail fast) instead of failing
later in the middle of a user request.
"""
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_prefix: JARVIS_LOG_LEVEL in the environment maps to `log_level` here.
    model_config = SettingsConfigDict(env_file=".env", env_prefix="JARVIS_", extra="ignore")

    log_level: str = "INFO"
    # Used when the user asks "what time is it?" without naming a place.
    default_timezone: str = "America/New_York"
    default_units: Literal["metric", "imperial"] = "imperial"

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
