"""Structured (JSON) logging with a per-request ID.

Why JSON: one log line = one machine-parseable event, so later we can filter
"all lines for request r_91c2" or "all get_weather failures" without regex.

Why contextvars: FastAPI is async — many requests interleave on one thread, so a
global variable would mix up request IDs. A ContextVar gives each request (each
asyncio task) its own value, and it's visible to every function that request calls.
"""
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes every LogRecord has; anything else was passed via `extra=` by us.
_STANDARD_ATTRS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        # Fields passed as logger.info("x", extra={"duration_ms": 12}) end up as
        # attributes on the record; copy them into the JSON object.
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS:
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Uvicorn's own access log duplicates our request log; silence it.
    logging.getLogger("uvicorn.access").disabled = True
