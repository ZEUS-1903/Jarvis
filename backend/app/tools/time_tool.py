from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from app.config import get_settings
from app.tools.base import Tool, ToolError


class TimeArgs(BaseModel):
    timezone: str | None = Field(
        default=None,
        description="IANA timezone name, e.g. 'America/New_York' or 'Asia/Tokyo'. "
        "Omit to use the user's local timezone.",
    )


class CurrentTimeTool(Tool):
    name = "get_current_time"
    description = (
        "Get the current date and time. Use whenever the answer depends on the "
        "current time or date; never guess it."
    )
    input_model = TimeArgs
    timeout_s = 1.0

    async def run(self, args: TimeArgs) -> dict[str, Any]:
        tz_name = args.timezone or get_settings().default_timezone
        try:
            tz = ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError):
            raise ToolError(f"unknown timezone '{tz_name}'; use an IANA name like 'Europe/London'")
        now = datetime.now(tz)
        return {
            "timezone": tz_name,
            "iso": now.isoformat(timespec="seconds"),
            "display": now.strftime("%A, %B %d, %Y, %H:%M"),
            "utc_offset": now.strftime("%z"),
        }
