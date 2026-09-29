from app.tools.base import Permission, Tool, ToolError, ToolResult
from app.google.client import GoogleClients
from app.memory.store import MemoryStore
from app.tools.calculator import CalculatorTool
from app.tools.google_tools import GetCalendarTool, ReadEmailTool, SearchEmailTool
from app.tools.memory_tools import ForgetTool, RememberTool
from app.tools.registry import ToolRegistry
from app.tools.time_tool import CurrentTimeTool
from app.tools.weather import WeatherTool


def build_default_registry(
    memories: MemoryStore | None = None, google: GoogleClients | None = None,
) -> ToolRegistry:
    tools = [CurrentTimeTool(), CalculatorTool(), WeatherTool()]
    if memories is not None:
        tools += [RememberTool(memories), ForgetTool(memories)]
    if google is not None:
        tools += [SearchEmailTool(google), ReadEmailTool(google), GetCalendarTool(google)]
    return ToolRegistry(tools)


__all__ = ["Permission", "Tool", "ToolError", "ToolResult", "ToolRegistry",
           "build_default_registry"]
