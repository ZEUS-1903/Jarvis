"""Weather tool tests with a fake HTTP transport: no network, deterministic."""
import httpx
import pytest

from app.tools.base import ToolError
from app.tools.weather import WeatherArgs, WeatherTool

BOSTON = {"name": "Boston", "latitude": 42.36, "longitude": -71.06,
          "admin1": "Massachusetts", "country": "United States"}
FORECAST = {
    "current": {"time": "2026-09-22T19:00", "temperature_2m": 57.2,
                "apparent_temperature": 55.0, "relative_humidity_2m": 70,
                "weather_code": 3, "wind_speed_10m": 8.1},
    "daily": {"temperature_2m_max": [63.0], "temperature_2m_min": [51.1],
              "precipitation_probability_max": [10]},
}


def make_tool(handler) -> WeatherTool:
    return WeatherTool(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_happy_path_imperial():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        if "geocoding" in request.url.host:
            return httpx.Response(200, json={"results": [BOSTON]})
        return httpx.Response(200, json=FORECAST)

    data = await make_tool(handler).run(WeatherArgs(location="Boston", units="imperial"))
    assert data["location"] == "Boston, Massachusetts, United States"
    assert data["temperature"] == 57.2 and data["temperature_unit"] == "°F"
    assert data["conditions"] == "overcast"
    assert data["precipitation_chance_percent"] == 10
    assert seen[1].params["temperature_unit"] == "fahrenheit"


async def test_city_state_falls_back_to_city_name():
    def handler(request):
        if "geocoding" in request.url.host:
            found = request.url.params["name"] == "Boston"
            return httpx.Response(200, json={"results": [BOSTON]} if found else {})
        return httpx.Response(200, json=FORECAST)

    data = await make_tool(handler).run(WeatherArgs(location="Boston, MA"))
    assert data["location"].startswith("Boston")


async def test_unknown_place():
    tool = make_tool(lambda r: httpx.Response(200, json={}))
    with pytest.raises(ToolError, match="couldn't find"):
        await tool.run(WeatherArgs(location="Atlantisville"))


async def test_upstream_500():
    tool = make_tool(lambda r: httpx.Response(503))
    with pytest.raises(ToolError, match="unavailable"):
        await tool.run(WeatherArgs(location="Boston"))


async def test_upstream_timeout():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ToolError, match="timed out"):
        await make_tool(handler).run(WeatherArgs(location="Boston"))


async def test_unexpected_shape():
    def handler(request):
        if "geocoding" in request.url.host:
            return httpx.Response(200, json={"results": [BOSTON]})
        return httpx.Response(200, json={"current": {}})

    with pytest.raises(ToolError, match="unexpected"):
        await make_tool(handler).run(WeatherArgs(location="Boston"))
