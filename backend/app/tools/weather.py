"""Current weather via Open-Meteo (free, no API key for non-commercial use).

Two HTTP calls:
  1. Geocoding:  place name -> latitude/longitude (+ country, region)
  2. Forecast:   lat/lon    -> current conditions + today's rain chance

The HTTP client is injected (constructor argument) so tests can swap in a fake
transport and never touch the network.
"""
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.config import get_settings
from app.tools.base import Tool, ToolError

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes, as used by Open-Meteo.
_WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "light freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "light freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "violent showers",
    85: "light snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
}


class WeatherArgs(BaseModel):
    location: str = Field(min_length=1, max_length=100,
                          description="City name, e.g. 'Boston' or 'Paris'.")
    units: Literal["metric", "imperial"] | None = Field(
        default=None, description="Omit to use the user's preferred units.")


class WeatherTool(Tool):
    name = "get_weather"
    description = (
        "Get current weather conditions and today's rain chance for a city. "
        "The result names the matched place; mention it if the city name is ambiguous."
    )
    input_model = WeatherArgs
    timeout_s = 10.0

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client

    async def run(self, args: WeatherArgs) -> dict[str, Any]:
        units = args.units or get_settings().default_units
        if self._client is not None:
            return await self._fetch(self._client, args.location, units)
        async with httpx.AsyncClient(timeout=5.0) as client:
            return await self._fetch(client, args.location, units)

    async def _fetch(self, client: httpx.AsyncClient, location: str, units: str) -> dict[str, Any]:
        place = await self._geocode(client, location)
        imperial = units == "imperial"
        params = {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                       "weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": 1,
            "temperature_unit": "fahrenheit" if imperial else "celsius",
            "wind_speed_unit": "mph" if imperial else "kmh",
        }
        body = await self._get_json(client, FORECAST_URL, params)
        try:
            current, daily = body["current"], body["daily"]
            return {
                "location": ", ".join(
                    p for p in (place.get("name"), place.get("admin1"), place.get("country")) if p
                ),
                "local_time": current.get("time"),
                "temperature": current["temperature_2m"],
                "feels_like": current.get("apparent_temperature"),
                "temperature_unit": "°F" if imperial else "°C",
                "conditions": _WMO_CODES.get(current.get("weather_code"), "unknown"),
                "humidity_percent": current.get("relative_humidity_2m"),
                "wind_speed": current.get("wind_speed_10m"),
                "wind_unit": "mph" if imperial else "km/h",
                "today_high": daily["temperature_2m_max"][0],
                "today_low": daily["temperature_2m_min"][0],
                "precipitation_chance_percent": daily["precipitation_probability_max"][0],
            }
        except (KeyError, IndexError, TypeError):
            raise ToolError("weather service returned an unexpected response")

    async def _geocode(self, client: httpx.AsyncClient, location: str) -> dict[str, Any]:
        # Open-Meteo's geocoder matches place names, so "Boston, MA" may find
        # nothing; fall back to the part before the first comma.
        candidates = [location]
        if "," in location:
            candidates.append(location.split(",")[0].strip())
        for name in candidates:
            body = await self._get_json(
                client, GEOCODE_URL, {"name": name, "count": 1, "language": "en", "format": "json"}
            )
            results = body.get("results") or []
            if results:
                return results[0]
        raise ToolError(f"couldn't find a place called '{location}'")

    async def _get_json(self, client: httpx.AsyncClient, url: str, params: dict) -> dict[str, Any]:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise ToolError("weather service timed out")
        except (httpx.HTTPError, ValueError):
            raise ToolError("weather service is unavailable")
