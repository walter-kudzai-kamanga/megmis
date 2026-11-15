from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from megmis.common.errors import ProviderError
from megmis.common.schemas import LatLon
from megmis.config import get_settings


class ValhallaRoutingProvider:
    name = "valhalla"

    def __init__(self) -> None:
        self.base = (get_settings().valhalla_url or "").rstrip("/")
        if not self.base:
            raise ProviderError("VALHALLA_URL not configured", retryable=False)

    def route(
        self,
        origin: LatLon,
        dest: LatLon,
        waypoints: list[LatLon],
        costing_profile: str,
        departure_time: datetime | None,
    ) -> list[dict[str, Any]]:
        costing = {
            "fastest": "auto",
            "safest": "auto",
            "cheapest": "auto",
            "fuel": "auto",
        }.get(costing_profile, "auto")
        locations = [{"lat": origin.lat, "lon": origin.lon}]
        locations.extend({"lat": w.lat, "lon": w.lon} for w in waypoints)
        locations.append({"lat": dest.lat, "lon": dest.lon})
        body = {"locations": locations, "costing": costing, "directions_options": {"units": "kilometers"}}
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.post(f"{self.base}/route", json=body)
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc), retryable=True) from exc
        trip = data.get("trip", {})
        summary = trip.get("summary", {})
        shape_len = summary.get("length", 0) * 1000
        duration = summary.get("time", 0)
        return [
            {
                "id": "valhalla-0",
                "label": "Valhalla route",
                "distance_m": shape_len,
                "duration_s": duration,
                "segments": [
                    {
                        "name": "valhalla",
                        "distance_m": shape_len,
                        "duration_s": duration,
                        "surface": "paved",
                        "weather": "clear",
                        "flood_exposure": 0.0,
                        "visibility_km": 12.0,
                        "wind_ms": 3.0,
                        "congestion": 0.2,
                        "incidents": [],
                    }
                ],
            }
        ]

    def matrix(
        self, sources: list[LatLon], targets: list[LatLon], profile: str
    ) -> dict[str, Any]:
        raise ProviderError("valhalla matrix not wired in Gen 2 MVP", retryable=False)


class GraphHopperRoutingProvider:
    name = "graphhopper"

    def __init__(self) -> None:
        self.base = (get_settings().graphhopper_url or "").rstrip("/")
        if not self.base:
            raise ProviderError("GRAPHHOPPER_URL not configured", retryable=False)

    def route(
        self,
        origin: LatLon,
        dest: LatLon,
        waypoints: list[LatLon],
        costing_profile: str,
        departure_time: datetime | None,
    ) -> list[dict[str, Any]]:
        points = [f"{origin.lat},{origin.lon}"]
        points.extend(f"{w.lat},{w.lon}" for w in waypoints)
        points.append(f"{dest.lat},{dest.lon}")
        params = [("point", p) for p in points] + [("profile", "car"), ("points_encoded", "false")]
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(f"{self.base}/route", params=params)
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc), retryable=True) from exc
        paths = data.get("paths") or []
        out = []
        for i, path in enumerate(paths[:3]):
            out.append(
                {
                    "id": f"gh-{i}",
                    "label": f"GraphHopper alt {i+1}",
                    "distance_m": path.get("distance", 0),
                    "duration_s": (path.get("time", 0) or 0) / 1000.0,
                    "segments": [
                        {
                            "name": "graphhopper",
                            "distance_m": path.get("distance", 0),
                            "duration_s": (path.get("time", 0) or 0) / 1000.0,
                            "surface": "paved",
                            "weather": "clear",
                            "flood_exposure": 0.0,
                            "visibility_km": 12.0,
                            "wind_ms": 3.0,
                            "congestion": 0.15,
                            "incidents": [],
                        }
                    ],
                }
            )
        return out

    def matrix(
        self, sources: list[LatLon], targets: list[LatLon], profile: str
    ) -> dict[str, Any]:
        raise ProviderError("graphhopper matrix not wired in Gen 2 MVP", retryable=False)


class OSRMRoutingProvider:
    name = "osrm"

    def __init__(self) -> None:
        self.base = (get_settings().osrm_url or "https://router.project-osrm.org").rstrip("/")

    def route(
        self,
        origin: LatLon,
        dest: LatLon,
        waypoints: list[LatLon],
        costing_profile: str,
        departure_time: datetime | None,
    ) -> list[dict[str, Any]]:
        coords = [f"{origin.lon},{origin.lat}"]
        coords.extend(f"{w.lon},{w.lat}" for w in waypoints)
        coords.append(f"{dest.lon},{dest.lat}")
        url = f"{self.base}/route/v1/driving/{';'.join(coords)}"
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(
                    url,
                    params={"overview": "full", "geometries": "geojson", "alternatives": "true"},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(str(exc), retryable=True) from exc
        out = []
        for i, route in enumerate(data.get("routes") or []):
            geom = []
            coords_geo = ((route.get("geometry") or {}).get("coordinates")) or []
            for lon, lat in coords_geo:
                geom.append([round(lat, 5), round(lon, 5)])
            out.append(
                {
                    "id": f"osrm-{i}",
                    "label": f"OSRM alt {i+1}",
                    "distance_m": route.get("distance", 0),
                    "duration_s": route.get("duration", 0),
                    "geometry": geom,
                    "algorithm": "osrm",
                    "segments": [
                        {
                            "name": "osrm",
                            "distance_m": route.get("distance", 0),
                            "duration_s": route.get("duration", 0),
                            "surface": "paved",
                            "weather": "clear",
                            "flood_exposure": 0.0,
                            "visibility_km": 12.0,
                            "wind_ms": 3.0,
                            "congestion": 0.1,
                            "incidents": [],
                        }
                    ],
                }
            )
        return out

    def matrix(
        self, sources: list[LatLon], targets: list[LatLon], profile: str
    ) -> dict[str, Any]:
        raise ProviderError("osrm matrix not wired in Gen 2 MVP", retryable=False)
