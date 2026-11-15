from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import Any


def _seed(lat: float, lon: float) -> int:
    raw = f"{lat:.3f}:{lon:.3f}".encode()
    return int(hashlib.md5(raw).hexdigest()[:8], 16)


class MockWeatherProvider:
    """Deterministic mock weather for Zimbabwe demo scenarios."""

    name = "mock-weather"

    def get_current(self, lat: float, lon: float) -> dict[str, Any]:
        s = _seed(lat, lon)
        precip = (s % 40) / 10.0
        condition = "heavy_rain" if precip >= 3.0 else "partly_cloudy" if precip >= 1.0 else "clear"
        return {
            "condition": condition,
            "temperature_c": 18 + (s % 15),
            "humidity": 45 + (s % 40),
            "wind": {"speed_ms": 2 + (s % 8), "direction_deg": s % 360},
            "precipitation": precip,
            "visibility_km": 4.0 if condition == "heavy_rain" else 12.0,
            "provider": self.name,
        }

    def get_forecast(self, lat: float, lon: float, days: int) -> list[dict[str, Any]]:
        s = _seed(lat, lon)
        out: list[dict[str, Any]] = []
        today = date.today()
        for i in range(days):
            day_seed = s + i * 17
            precip_prob = (day_seed % 90) / 100.0
            condition = "rain" if precip_prob > 0.55 else "clouds" if precip_prob > 0.3 else "clear"
            out.append(
                {
                    "date": (today + timedelta(days=i)).isoformat(),
                    "min": 12 + (day_seed % 6),
                    "max": 22 + (day_seed % 10),
                    "condition": condition,
                    "precipitation_prob": precip_prob,
                }
            )
        return out

    def get_hourly(self, lat: float, lon: float, on_date: date) -> list[dict[str, Any]]:
        s = _seed(lat, lon)
        hours: list[dict[str, Any]] = []
        for h in range(24):
            hours.append(
                {
                    "time": datetime(on_date.year, on_date.month, on_date.day, h, tzinfo=UTC).isoformat(),
                    "temp": 15 + ((s + h) % 12),
                    "precip_prob": ((s + h * 3) % 100) / 100.0,
                    "wind": 2 + ((s + h) % 6),
                }
            )
        return hours

    def get_historical(
        self, lat: float, lon: float, start: date, end: date
    ) -> list[dict[str, Any]]:
        s = _seed(lat, lon)
        records: list[dict[str, Any]] = []
        cur = start
        i = 0
        while cur <= end:
            records.append(
                {
                    "date": cur.isoformat(),
                    "observations": {
                        "temp_avg_c": 16 + ((s + i) % 10),
                        "rainfall_mm": (s + i) % 25,
                    },
                }
            )
            cur += timedelta(days=1)
            i += 1
        return records

    def get_alerts(self, lat: float, lon: float) -> list[dict[str, Any]]:
        s = _seed(lat, lon)
        now = datetime.now(UTC)
        alerts: list[dict[str, Any]] = []
        if s % 3 == 0:
            alerts.append(
                {
                    "type": "heavy_rain",
                    "severity": "moderate",
                    "source": "model",
                    "official": False,
                    "valid_from": now.isoformat(),
                    "valid_to": (now + timedelta(hours=12)).isoformat(),
                }
            )
        if s % 7 == 0:
            alerts.append(
                {
                    "type": "flood_warning",
                    "severity": "severe",
                    "source": "national_met",
                    "official": True,
                    "valid_from": now.isoformat(),
                    "valid_to": (now + timedelta(hours=24)).isoformat(),
                }
            )
        return alerts
