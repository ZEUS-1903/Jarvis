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

    # Text-to-speech (Kokoro, runs locally). Model files are downloaded once;
    # see README "Voice setup". Paths are relative to the backend/ folder.
    tts_model_path: str = "models/kokoro-v1.0.onnx"
    tts_voices_path: str = "models/voices-v1.0.bin"
    # One voice ("af_heart") or a blend ("am_michael:60,bm_george:40").
    tts_voice: str = "af_heart"
    tts_speed: float = 1.0

    # Speech-to-text (Whisper via faster-whisper, runs locally). The model is
    # downloaded automatically on first use. "base.en" (~150 MB) is fast;
    # "small.en" (~480 MB) is more accurate but slower.
    stt_model: str = "base.en"
    stt_compute_type: str = "int8"  # 8-bit weights: ~4x less memory, fast on CPU

    # Wake word ("hey jarvis", openWakeWord, runs locally). Score 0..1 per 80 ms of audio;
    # raise the threshold if it triggers by itself, lower it if it misses you.
    wake_model: str = "hey_jarvis"
    wake_threshold: float = 0.5
    # Browser pages allowed to open the wake-word WebSocket (see api/voice.py).
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Google (Gmail + Calendar). The OAuth client file comes from Google Cloud
    # Console (Desktop app); see README "Gmail & Calendar".
    google_client_file: str = "secrets/google_client.json"

    # PostgreSQL. Homebrew's default user is your macOS login with no password,
    # so "postgresql://localhost/jarvis" works after `createdb jarvis`.
    database_url: str = "postgresql://localhost:5432/jarvis"

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
