from __future__ import annotations

from typing import Any

from bot.connectors.base import ConnectorError, HttpGet, default_get

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# https://open-meteo.com/en/docs -> WMO weather interpretation codes (condensed)
_WMO = {
    0: "clear",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "freezing fog",
    51: "light drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "rain showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
}


class WeatherConnector:
    """Keyless daily forecast via Open-Meteo."""

    name = "weather"

    def __init__(self, get: HttpGet | None = None) -> None:
        self._get = get or default_get

    async def fetch(self, params: dict[str, Any]) -> str:
        location = str(params.get("location", "")).strip()
        if not location:
            raise ConnectorError("weather: no location configured")

        lat, lon, label = await self._geocode(location)
        resp = await self._get(
            _FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "timezone": "auto",
                "forecast_days": 1,
            },
        )
        resp.raise_for_status()
        daily = resp.json().get("daily") or {}
        try:
            high = daily["temperature_2m_max"][0]
            low = daily["temperature_2m_min"][0]
            precip = daily["precipitation_probability_max"][0]
            code = daily["weather_code"][0]
        except (KeyError, IndexError) as exc:
            raise ConnectorError("weather: unexpected forecast response") from exc

        condition = _WMO.get(int(code), "mixed")
        return (
            f"Weather for {label}: {condition}, "
            f"high {high}° / low {low}°, precip {precip}%."
        )

    async def _geocode(self, location: str) -> tuple[float, float, str]:
        resp = await self._get(_GEOCODE_URL, params={"name": location, "count": 1})
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            raise ConnectorError(f"weather: could not geocode {location!r}")
        top = results[0]
        country = top.get("country_code") or top.get("country") or ""
        label = f"{top.get('name', location)}, {country}".rstrip(", ")
        return top["latitude"], top["longitude"], label
