"""FastAPI entry point: builds the app, wires middleware and routers."""
import logging
import time
import uuid

from fastapi import FastAPI, Request

from app.api import health
from app.config import get_settings
from app.observability.logging import request_id_var, setup_logging

logger = logging.getLogger("jarvis.http")


def create_app() -> FastAPI:
    settings = get_settings()  # raises at startup if config is invalid
    setup_logging(settings.log_level)

    app = FastAPI(title="JARVIS", version="0.1.0")

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
    logger.info("app.started", extra={"default_timezone": settings.default_timezone})
    return app


app = create_app()
