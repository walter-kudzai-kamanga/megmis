from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from megmis.common.errors import ProviderError
from megmis.config import get_settings


class OpenMeteoWeatherProvider:
    name = "open-meteo"

    def __init__(self) -> None:
        self.base = get_settings().open_meteo_base_url.rstrip("/")

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(f"{self.base}{path}", params=params)
                r.raise_for_status()
                return r.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc), retryable=True, code="PROVIDER_UNAVAILABLE") from exc

    def get_current(self, lat: float, lon: float) -> dict[str, Any]:
        data = self._get(
            "/v1/forecast",
            {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,visibility",
            },
        )
        cur = data.get("current", {})
        code = cur.get("weather_code", 0)
        condition = "rain" if code >= 51 else "clouds" if code >= 1 else "clear"
        return {
            "condition": condition,
            "temperature_c": cur.get("temperature_2m"),
            "humidity": cur.get("relative_humidity_2m"),
            "wind": {"speed_ms": (cur.get("wind_speed_10m") or 0) / 3.6, "direction_deg": 0},
            "precipitation": cur.get("precipitation") or 0,
            "visibility_km": (cur.get("visibility") or 10000) / 1000,
            "provider": self.name,
        }

    def get_forecast(self, lat: float, lon: float, days: int) -> list[dict[str, Any]]:
        data = self._get(
            "/v1/forecast",
            {
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "forecast_days": days,
            },
        )
        daily = data.get("daily", {})
        out = []
        for i, d in enumerate(daily.get("time", [])):
            code = (daily.get("weather_code") or [0])[i]
            out.append(
                {
                    "date": d,
                    "min": (daily.get("temperature_2m_min") or [None])[i],
                    "max": (daily.get("temperature_2m_max") or [None])[i],
                    "condition": "rain" if code >= 51 else "clouds" if code >= 1 else "clear",
                    "precipitation_prob": ((daily.get("precipitation_probability_max") or [0])[i] or 0)
                    / 100.0,
                }
            )
        return out

    def get_hourly(self, lat: float, lon: float, on_date: date) -> list[dict[str, Any]]:
        data = self._get(
            "/v1/forecast",
            {
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,precipitation_probability,wind_speed_10m",
                "start_date": on_date.isoformat(),
                "end_date": on_date.isoformat(),
            },
        )
        hourly = data.get("hourly", {})
        out = []
        for i, t in enumerate(hourly.get("time", [])):
            out.append(
                {
                    "time": t,
                    "temp": (hourly.get("temperature_2m") or [None])[i],
                    "precip_prob": ((hourly.get("precipitation_probability") or [0])[i] or 0) / 100.0,
                    "wind": ((hourly.get("wind_speed_10m") or [0])[i] or 0) / 3.6,
                }
            )
        return out

    def get_historical(
        self, lat: float, lon: float, start: date, end: date
    ) -> list[dict[str, Any]]:
        data = self._get(
            "/v1/archive",
            {
                "latitude": lat,
                "longitude": lon,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": "temperature_2m_mean,precipitation_sum",
            },
        )
        daily = data.get("daily", {})
        out = []
        for i, d in enumerate(daily.get("time", [])):
            out.append(
                {
                    "date": d,
                    "observations": {
                        "temp_avg_c": (daily.get("temperature_2m_mean") or [None])[i],
                        "rainfall_mm": (daily.get("precipitation_sum") or [None])[i],
                    },
                }
            )
        return out

    def get_alerts(self, lat: float, lon: float) -> list[dict[str, Any]]:
        # Open-Meteo free tier has limited official alerts; return empty model list.
        return []
