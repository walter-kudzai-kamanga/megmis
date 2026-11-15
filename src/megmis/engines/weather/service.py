from __future__ import annotations

from datetime import date
from typing import Any

from megmis.common.errors import AppError
from megmis.common.schemas import (
    Confidence,
    Envelope,
    LocationInput,
    OfficialVsModel,
    Provenance,
    new_request_id,
)
from megmis.common.zimbabwe import lookup_place
from megmis.db.redis_cache import weather_cache_get, weather_cache_set
from megmis.providers.factory import get_geocoding_provider, get_weather_provider

ACTIVITY_RULES: dict[str, dict[str, Any]] = {
    "outdoor_wedding": {
        "rain_threshold": 0.4,
        "wind_threshold": 8,
        "high_risk_conditions": {"heavy_rain", "storm", "flood_warning"},
    },
    "road_trip": {
        "rain_threshold": 0.6,
        "wind_threshold": 12,
        "high_risk_conditions": {"heavy_rain", "flood_warning"},
    },
    "construction": {
        "rain_threshold": 0.5,
        "wind_threshold": 10,
        "high_risk_conditions": {"heavy_rain", "storm", "high_wind"},
    },
    "farming": {
        "rain_threshold": 0.7,
        "wind_threshold": 15,
        "high_risk_conditions": {"storm"},
    },
}


class WeatherService:
    def __init__(self) -> None:
        self.weather = get_weather_provider()
        self.geocode = get_geocoding_provider()

    def resolve_location(self, location: LocationInput) -> tuple[float, float, str | None]:
        if location.has_coords():
            assert location.lat is not None and location.lon is not None
            return location.lat, location.lon, location.name
        if location.name:
            coords = lookup_place(location.name)
            if coords:
                return coords[0], coords[1], location.name
            points = self.geocode.geocode(location.name)
            return points[0].lat, points[0].lon, location.name
        raise AppError("INVALID_LOCATION", "Provide lat/lon or name")

    def _prov(
        self,
        *,
        confidence: Confidence = Confidence.medium,
        official: OfficialVsModel = OfficialVsModel.model_derived,
    ) -> Provenance:
        return Provenance(
            data_source=getattr(self.weather, "name", "weather"),
            confidence=confidence,
            official_vs_model=official,
        )

    def current(self, location: LocationInput) -> Envelope[dict[str, Any]]:
        from megmis.config import get_settings

        lat, lon, _ = self.resolve_location(location)
        provider = getattr(self.weather, "name", "weather")
        if get_settings().use_persistence:
            cached = weather_cache_get(provider, lat, lon)
            if cached:
                return Envelope(data=cached, provenance=self._prov(), request_id=new_request_id())
        data = self.weather.get_current(lat, lon)
        if get_settings().use_persistence:
            weather_cache_set(provider, lat, lon, data)
        return Envelope(data=data, provenance=self._prov(), request_id=new_request_id())

    def forecast(self, location: LocationInput, days: int = 7) -> Envelope[dict[str, Any]]:
        days = max(1, min(14, days))
        lat, lon, _ = self.resolve_location(location)
        daily = self.weather.get_forecast(lat, lon, days)
        return Envelope(
            data={"daily": daily},
            provenance=self._prov(confidence=Confidence.forecast_dependent),
            request_id=new_request_id(),
        )

    def hourly(self, location: LocationInput, on_date: date) -> Envelope[dict[str, Any]]:
        lat, lon, _ = self.resolve_location(location)
        hourly = self.weather.get_hourly(lat, lon, on_date)
        return Envelope(
            data={"hourly": hourly},
            provenance=self._prov(confidence=Confidence.forecast_dependent),
            request_id=new_request_id(),
        )

    def alerts(self, location: LocationInput) -> Envelope[dict[str, Any]]:
        lat, lon, _ = self.resolve_location(location)
        alerts = self.weather.get_alerts(lat, lon)
        has_official = any(a.get("official") for a in alerts)
        has_model = any(not a.get("official") for a in alerts)
        if has_official and has_model:
            label = OfficialVsModel.mixed
        elif has_official:
            label = OfficialVsModel.official
        else:
            label = OfficialVsModel.model_derived
        return Envelope(
            data={"alerts": alerts},
            provenance=self._prov(official=label),
            request_id=new_request_id(),
        )

    def compare(self, locations: list[LocationInput]) -> Envelope[dict[str, Any]]:
        comparison = []
        for loc in locations:
            cur = self.current(loc)
            comparison.append(
                {
                    "location": loc.model_dump(exclude_none=True),
                    "summary": {
                        "condition": cur.data.get("condition"),
                        "temperature_c": cur.data.get("temperature_c"),
                        "precipitation": cur.data.get("precipitation"),
                    },
                }
            )
        return Envelope(data={"comparison": comparison}, provenance=self._prov(), request_id=new_request_id())

    def historical(
        self, location: LocationInput, start: date, end: date
    ) -> Envelope[dict[str, Any]]:
        lat, lon, _ = self.resolve_location(location)
        records = self.weather.get_historical(lat, lon, start, end)
        return Envelope(data={"records": records}, provenance=self._prov(), request_id=new_request_id())

    def air_quality(self, location: LocationInput) -> Envelope[dict[str, Any]]:
        lat, lon, _ = self.resolve_location(location)
        s = abs(int(lat * 1000) + int(lon * 1000))
        data = {
            "aqi": 30 + (s % 70),
            "pollutants": {"pm25": 8 + (s % 40), "pm10": 15 + (s % 50), "o3": 20 + (s % 30)},
        }
        return Envelope(data=data, provenance=self._prov(confidence=Confidence.low), request_id=new_request_id())

    def agricultural(self, location: LocationInput) -> Envelope[dict[str, Any]]:
        cur = self.current(location)
        data = {
            "rainfall_mm": cur.data.get("precipitation", 0) * 5,
            "humidity": cur.data.get("humidity"),
            "soil_moisture": None,
            "growing_conditions": "favourable"
            if cur.data.get("condition") == "clear"
            else "caution",
        }
        return Envelope(data=data, provenance=self._prov(), request_id=new_request_id())

    def analyze_risk(
        self, location: LocationInput, activity: str, on_date: date | None = None
    ) -> Envelope[dict[str, Any]]:
        cur = self.current(location)
        alerts = self.alerts(location)
        rules = ACTIVITY_RULES.get(activity, ACTIVITY_RULES["road_trip"])
        condition = cur.data.get("condition", "unknown")
        precip = float(cur.data.get("precipitation") or 0)
        wind = float((cur.data.get("wind") or {}).get("speed_ms") or 0)

        score = 0.2
        recommendations: list[str] = []
        if condition in rules["high_risk_conditions"] or precip >= 3.0:
            score += 0.45
            recommendations.append("High precipitation risk — consider rescheduling outdoor plans.")
        if precip / 5.0 >= rules["rain_threshold"]:
            score += 0.15
            recommendations.append("Elevated rain probability for this activity.")
        if wind >= rules["wind_threshold"]:
            score += 0.15
            recommendations.append("Wind may disrupt outdoor setups.")
        if any(a.get("official") for a in alerts.data.get("alerts", [])):
            score += 0.2
            recommendations.append("Official weather warning in effect — follow national guidance.")

        score = min(1.0, score)
        level = "high" if score >= 0.7 else "moderate" if score >= 0.4 else "low"
        if not recommendations:
            recommendations.append("Conditions look suitable; continue monitoring forecasts.")

        data = {
            "weather_assessment": {
                "activity": activity,
                "date": (on_date or date.today()).isoformat(),
                "condition": condition,
                "risk_level": level,
                "score": round(score, 2),
                "indicators": {
                    "precipitation": precip,
                    "wind_ms": wind,
                    "alerts": alerts.data.get("alerts", []),
                },
            },
            "recommendations": recommendations,
            "confidence": "medium",
        }
        official = OfficialVsModel.mixed if any(
            a.get("official") for a in alerts.data.get("alerts", [])
        ) else OfficialVsModel.model_derived
        return Envelope(
            data=data,
            provenance=self._prov(official=official),
            request_id=new_request_id(),
        )

    def recommend_activities(
        self, location: LocationInput, on_date: date | None = None
    ) -> Envelope[dict[str, Any]]:
        activities = ["outdoor_wedding", "road_trip", "construction", "farming", "hiking"]
        recs = []
        for act in activities:
            risk = self.analyze_risk(location, act, on_date)
            level = risk.data["weather_assessment"]["risk_level"]
            suitability = {"low": "high", "moderate": "medium", "high": "low"}[level]
            recs.append(
                {
                    "activity": act,
                    "suitability": suitability,
                    "reasons": risk.data["recommendations"][:2],
                }
            )
        return Envelope(
            data={"recommendations": recs, "date": (on_date or date.today()).isoformat()},
            provenance=self._prov(confidence=Confidence.forecast_dependent),
            request_id=new_request_id(),
        )
