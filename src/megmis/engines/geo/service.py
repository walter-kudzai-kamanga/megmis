from __future__ import annotations

import math
from typing import Any

from megmis.common.schemas import (
    Confidence,
    Envelope,
    LatLon,
    LocationInput,
    Provenance,
    new_request_id,
)
from megmis.engines.weather.service import WeatherService
from megmis.providers.factory import get_geocoding_provider

# Simple POI seed for Gen 1 demos
POIS: list[dict[str, Any]] = [
    {"name": "Parirenyatwa Hospital", "category": "hospital", "lat": -17.8200, "lon": 31.0400, "contact": "+263-4-000000"},
    {"name": "Harare Central Police", "category": "police", "lat": -17.8270, "lon": 31.0520, "contact": "+263-4-000001"},
    {"name": "United Bulawayo Hospitals", "category": "hospital", "lat": -20.1500, "lon": 28.5800, "contact": "+263-9-000000"},
    {"name": "Mutare Provincial Hospital", "category": "hospital", "lat": -18.9750, "lon": 32.6700, "contact": "+263-20-000000"},
    {"name": "Victoria Falls Fire Station", "category": "fire", "lat": -17.9300, "lon": 25.8400, "contact": "+263-13-000000"},
    {"name": "Shell Avondale", "category": "fuel", "lat": -17.8000, "lon": 31.0350, "contact": None},
]


def _dist_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    r = 6371000.0
    phi1, phi2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlambda = math.radians(b_lon - a_lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class GeoService:
    def __init__(self) -> None:
        self.geocode_provider = get_geocoding_provider()
        self.weather = WeatherService()

    def _prov(self, provider: Any | None = None) -> Provenance:
        src = provider if provider is not None else self.geocode_provider
        return Provenance(
            data_source=getattr(src, "name", "geo"),
            confidence=Confidence.high,
        )

    def _invoke(self, method: str, *args: Any):
        """Call geocode adapter with primary→fallback failover on ProviderError."""
        from megmis.providers.orchestrator import get_orchestrator

        return get_orchestrator().invoke("geocode", method, *args)

    def geocode(self, address: str) -> Envelope[dict[str, Any]]:
        points, provider = self._invoke("geocode", address)
        return Envelope(
            data={"results": [p.model_dump() for p in points]},
            provenance=self._prov(provider),
            request_id=new_request_id(),
        )

    def reverse(self, lat: float, lon: float) -> Envelope[dict[str, Any]]:
        result, provider = self._invoke("reverse", lat, lon)
        return Envelope(data=result, provenance=self._prov(provider), request_id=new_request_id())

    def nearby(
        self, location: LocationInput, category: str | None = None, radius_m: int = 5000
    ) -> Envelope[dict[str, Any]]:
        lat, lon, _ = self.weather.resolve_location(location)
        places = []
        for poi in POIS:
            if category and poi["category"] != category:
                continue
            d = _dist_m(lat, lon, poi["lat"], poi["lon"])
            if d <= radius_m:
                places.append({**poi, "distance_m": round(d)})
        places.sort(key=lambda p: p["distance_m"])
        return Envelope(data={"places": places}, provenance=self._prov(), request_id=new_request_id())

    def emergency(self, location: LocationInput, facility_type: str | None = None) -> Envelope[dict[str, Any]]:
        types = {"hospital", "police", "fire"}
        category = facility_type if facility_type in types else None
        nearby = self.nearby(location, category=category, radius_m=50_000)
        facilities = [
            {
                "name": p["name"],
                "type": p["category"],
                "contact": p.get("contact"),
                "lat": p["lat"],
                "lon": p["lon"],
                "distance_m": p["distance_m"],
            }
            for p in nearby.data["places"]
            if p["category"] in types
        ]
        return Envelope(
            data={"facilities": facilities},
            provenance=self._prov(),
            request_id=new_request_id(),
        )

    def resolve_latlon(self, location: LocationInput) -> LatLon:
        lat, lon, _ = self.weather.resolve_location(location)
        return LatLon(lat=lat, lon=lon)
