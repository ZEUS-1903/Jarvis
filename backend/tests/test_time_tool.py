from datetime import datetime

import pytest

from app.tools.base import ToolError
from app.tools.time_tool import CurrentTimeTool, TimeArgs

tool = CurrentTimeTool()


async def test_explicit_timezone():
    data = await tool.run(TimeArgs(timezone="Asia/Tokyo"))
    assert data["timezone"] == "Asia/Tokyo"
    assert data["utc_offset"] == "+0900"  # Japan has no DST
    datetime.fromisoformat(data["iso"])   # parses cleanly


async def test_default_timezone_from_settings():
    data = await tool.run(TimeArgs())
    assert data["timezone"] == "America/New_York"


async def test_unknown_timezone():
    with pytest.raises(ToolError, match="unknown timezone"):
        await tool.run(TimeArgs(timezone="EST5EDTX"))


async def test_human_friendly_fields():
    data = await tool.run(TimeArgs(timezone="UTC"))
    assert data["time"].endswith(("AM", "PM")) and not data["time"].startswith("0")
    assert data["date"].count(",") == 2  # "Monday, September 28, 2026"
