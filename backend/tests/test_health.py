import json
import logging

import pytest

from tests.fakes import make_test_app
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.observability.logging import JsonFormatter, request_id_var


def test_health_returns_ok_and_request_id():
    client = TestClient(make_test_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"].startswith("r_")


def test_json_formatter_includes_request_id_and_extra_fields():
    record = logging.makeLogRecord(
        {"name": "t", "levelname": "INFO", "msg": "tool.executed", "duration_ms": 12}
    )
    token = request_id_var.set("r_test")
    try:
        entry = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert entry["event"] == "tool.executed"
    assert entry["request_id"] == "r_test"
    assert entry["duration_ms"] == 12


def test_invalid_timezone_fails_fast():
    with pytest.raises(ValidationError):
        Settings(default_timezone="Mars/Olympus_Mons")
