"""FastAPI entry point: builds the app, wires middleware and routers."""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.agent.loop import Agent
from app.api import chat, health, voice
from app.api import memories as memories_api
from app.config import get_settings
from app.conversation.store import ConversationStore, PostgresConversationStore
from app.db.database import make_pool, migrate, open_pool
from app.memory.store import MemoryStore, PostgresMemoryStore
from app.llm.base import LLMClient
from app.llm.openai_compat import OpenAICompatClient
from app.observability.logging import request_id_var, setup_logging
from app.tools import build_default_registry
from app.voice.stt import FasterWhisperSTT, STTEngine
from app.voice.tts import KokoroTTS, TTSEngine

logger = logging.getLogger("jarvis.http")


def create_app(
    llm: LLMClient | None = None, tts: TTSEngine | None = None, stt: STTEngine | None = None,
    store: ConversationStore | None = None, memories: MemoryStore | None = None,
) -> FastAPI:
    """Build the app. Tests pass fakes; normally we build the real engines."""
    settings = get_settings()  # raises at startup if config is invalid
    setup_logging(settings.log_level)

    if llm is None:
        llm = OpenAICompatClient(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key.get_secret_value() if settings.llm_api_key else None,
            timeout_s=settings.llm_timeout_s,
        )

    # Real Postgres stores unless tests injected in-memory ones.
    pool = None
    if store is None or memories is None:
        pool = make_pool(settings.database_url)
        store = store or PostgresConversationStore(pool, max_messages=settings.history_max_messages)
        memories = memories or PostgresMemoryStore(pool)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if pool is not None:
            # Fail fast with a helpful message if Postgres isn't reachable,
            # then bring the schema up to date.
            await open_pool(pool, settings.database_url)
            await migrate(pool)
        yield  # the app serves requests here
        if pool is not None:
            await pool.close()
        if hasattr(llm, "aclose"):
            await llm.aclose()  # close pooled HTTP connections on shutdown

    app = FastAPI(title="JARVIS", version="0.1.0", lifespan=lifespan)
    # One shared instance of each, reused by every request.
    app.state.store = store
    app.state.memories = memories
    app.state.tts = tts or KokoroTTS(
        settings.tts_model_path, settings.tts_voices_path,
        default_voice=settings.tts_voice, speed=settings.tts_speed,
    )
    app.state.stt = stt or FasterWhisperSTT(settings.stt_model, settings.stt_compute_type)
    app.state.agent = Agent(
        llm, build_default_registry(memories),
        timezone=settings.default_timezone, units=settings.default_units,
        location=settings.default_location,
        max_iterations=settings.agent_max_iterations, memories=memories,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        # 1. Give this request an ID and put it in the context var, so every log
        #    line written while handling it carries the same request_id.
        request_id = f"r_{uuid.uuid4().hex[:12]}"
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("http.unhandled_error", extra={"path": request.url.path})
                raise
            # 2. Return the ID to the client so a bug report can quote it.
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "http.request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
            return response
        finally:
            request_id_var.reset(token)  # don't leak into the next request

    app.include_router(health.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(voice.router, prefix="/api")
    app.include_router(memories_api.router, prefix="/api")
    logger.info("app.started", extra={"model": llm.model, "llm_url": settings.llm_base_url,
                                      "default_timezone": settings.default_timezone})
    return app


app = create_app()
