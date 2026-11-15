from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from megmis.common.errors import ProviderError
from megmis.config import get_settings


class OpenWeatherProvider:
    name = "openweather"

    def __init__(self) -> None:
        self.key = get_settings().openweather_key
        if not self.key:
            raise ProviderError("OPENWEATHER_KEY not configured", retryable=False)

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {**params, "appid": self.key, "units": "metric"}
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(f"https://api.openweathermap.org{path}", params=params)
                r.raise_for_status()
                return r.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc), retryable=True, code="PROVIDER_UNAVAILABLE") from exc

    def get_current(self, lat: float, lon: float) -> dict[str, Any]:
        data = self._get("/data/2.5/weather", {"lat": lat, "lon": lon})
        weather = (data.get("weather") or [{}])[0]
        return {
            "condition": weather.get("main", "unknown").lower(),
            "temperature_c": data.get("main", {}).get("temp"),
            "humidity": data.get("main", {}).get("humidity"),
            "wind": {
                "speed_ms": data.get("wind", {}).get("speed"),
                "direction_deg": data.get("wind", {}).get("deg"),
            },
            "precipitation": (data.get("rain") or {}).get("1h", 0),
            "visibility_km": (data.get("visibility") or 10000) / 1000,
            "provider": self.name,
        }

    def get_forecast(self, lat: float, lon: float, days: int) -> list[dict[str, Any]]:
        data = self._get("/data/2.5/forecast", {"lat": lat, "lon": lon, "cnt": min(40, days * 8)})
        by_day: dict[str, list] = {}
        for item in data.get("list", []):
            d = item["dt_txt"][:10]
            by_day.setdefault(d, []).append(item)
        out = []
        for d, items in list(by_day.items())[:days]:
            temps = [i["main"]["temp"] for i in items]
            pop = max(i.get("pop", 0) for i in items)
            cond = items[0]["weather"][0]["main"].lower()
            out.append(
                {
                    "date": d,
                    "min": min(temps),
                    "max": max(temps),
                    "condition": cond,
                    "precipitation_prob": pop,
                }
            )
        return out

    def get_hourly(self, lat: float, lon: float, on_date: date) -> list[dict[str, Any]]:
        data = self._get("/data/2.5/forecast", {"lat": lat, "lon": lon})
        out = []
        for item in data.get("list", []):
            if item["dt_txt"].startswith(on_date.isoformat()):
                out.append(
                    {
                        "time": item["dt_txt"],
                        "temp": item["main"]["temp"],
                        "precip_prob": item.get("pop", 0),
                        "wind": item.get("wind", {}).get("speed"),
                    }
                )
        return out

    def get_historical(
        self, lat: float, lon: float, start: date, end: date
    ) -> list[dict[str, Any]]:
        # OpenWeather historical requires paid One Call; return sparse synthetic fallback note
        raise ProviderError("historical requires One Call paid tier", retryable=False)

    def get_alerts(self, lat: float, lon: float) -> list[dict[str, Any]]:
        # Best-effort via One Call if available; otherwise empty
        try:
            data = self._get(
                "/data/3.0/onecall",
                {"lat": lat, "lon": lon, "exclude": "minutely,hourly,daily"},
            )
        except ProviderError:
            return []
        alerts = []
        now = datetime.now(timezone.utc)
        for a in data.get("alerts", []):
            alerts.append(
                {
                    "type": a.get("event", "alert"),
                    "severity": "severe",
                    "source": a.get("sender_name", "openweather"),
                    "official": True,
                    "valid_from": datetime.fromtimestamp(a.get("start", now.timestamp()), tz=timezone.utc).isoformat(),
                    "valid_to": datetime.fromtimestamp(a.get("end", (now + timedelta(hours=6)).timestamp()), tz=timezone.utc).isoformat(),
                }
            )
        return alerts
