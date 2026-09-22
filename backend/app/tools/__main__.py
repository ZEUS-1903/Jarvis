"""Run a tool by hand, through the same registry the agent will use.

    uv run python -m app.tools calculate '{"expression": "2**10"}'
    uv run python -m app.tools get_weather '{"location": "Boston"}'
"""
import asyncio
import json
import sys

from app.config import get_settings
from app.observability.logging import setup_logging
from app.tools import build_default_registry


async def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    setup_logging(get_settings().log_level)
    result = await build_default_registry().execute(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


asyncio.run(main())
