from app.tools.base import Permission, Tool, ToolError, ToolResult
from app.tools.calculator import CalculatorTool
from app.tools.registry import ToolRegistry
from app.tools.time_tool import CurrentTimeTool
from app.tools.weather import WeatherTool


def build_default_registry() -> ToolRegistry:
    return ToolRegistry([CurrentTimeTool(), CalculatorTool(), WeatherTool()])


__all__ = ["Permission", "Tool", "ToolError", "ToolResult", "ToolRegistry",
           "build_default_registry"]
