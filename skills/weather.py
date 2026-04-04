from __future__ import annotations

from typing import Any, Dict

import requests

from skills.base import BaseSkill


class WeatherSkill(BaseSkill):
    """Fetches current weather for a given city using the free Open-Meteo API (no API key needed)."""

    name = "weather"
    description = "Get current weather (temperature, wind, humidity) for a city. No API key required."
    parameters = {
        "city": {"type": "string", "description": "City name, e.g. 'London'", "required": True},
    }

    def execute(self, city: str, **kwargs) -> Dict[str, Any]:
        # Step 1: geocode the city name
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en"},
            timeout=10,
        )
        geo.raise_for_status()
        results = geo.json().get("results")
        if not results:
            return {"error": f"City '{city}' not found"}

        loc = results[0]
        lat, lon = loc["latitude"], loc["longitude"]
        resolved_name = loc.get("name", city)
        country = loc.get("country", "")

        # Step 2: fetch current weather
        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
                "hourly": "relative_humidity_2m",
                "timezone": "auto",
            },
            timeout=10,
        )
        weather.raise_for_status()
        data = weather.json()
        cw = data.get("current_weather", {})

        humidity_values = data.get("hourly", {}).get("relative_humidity_2m", [])
        humidity = humidity_values[0] if humidity_values else None

        return {
            "city": resolved_name,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "temperature_c": cw.get("temperature"),
            "windspeed_kmh": cw.get("windspeed"),
            "wind_direction_deg": cw.get("winddirection"),
            "weather_code": cw.get("weathercode"),
            "humidity_percent": humidity,
            "time": cw.get("time"),
        }
