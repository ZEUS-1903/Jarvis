"""FastAPI entry point: builds the app, wires middleware and routers."""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.agent.loop import Agent
from app.api import chat, health
from app.config import get_settings
from app.conversation.store import InMemoryConversationStore
from app.llm.base import LLMClient
from app.llm.openai_compat import OpenAICompatClient
from app.observability.logging import request_id_var, setup_logging
from app.tools import build_default_registry

logger = logging.getLogger("jarvis.http")


def create_app(llm: LLMClient | None = None) -> FastAPI:
    """Build the app. Tests pass a fake `llm`; normally we build the real one."""
    settings = get_settings()  # raises at startup if config is invalid
    setup_logging(settings.log_level)

    if llm is None:
        llm = OpenAICompatClient(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key.get_secret_value() if settings.llm_api_key else None,
            timeout_s=settings.llm_timeout_s,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield  # the app serves requests here
        if hasattr(llm, "aclose"):
            await llm.aclose()  # close pooled HTTP connections on shutdown

    app = FastAPI(title="JARVIS", version="0.1.0", lifespan=lifespan)
    # One shared instance of each, reused by every request.
    app.state.store = InMemoryConversationStore(max_messages=settings.history_max_messages)
    app.state.agent = Agent(
        llm, build_default_registry(),
        timezone=settings.default_timezone, units=settings.default_units,
        location=settings.default_location,
        max_iterations=settings.agent_max_iterations,
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
    logger.info("app.started", extra={"model": llm.model, "llm_url": settings.llm_base_url,
                                      "default_timezone": settings.default_timezone})
    return app


app = create_app()
