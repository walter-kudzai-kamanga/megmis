"""Mock routing provider — Dijkstra over the Zimbabwe highway graph."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from megmis.common.schemas import LatLon
from megmis.common.zw_graph import haversine_m, route_candidates


class MockRoutingProvider:
    """
    Returns ranked corridor candidates from Dijkstra on the Zimbabwe graph.
    Profiles (safest / fastest / fuel / cheapest) change edge weights.
    """

    name = "mock-routing-dijkstra"

    def route(
        self,
        origin: LatLon,
        dest: LatLon,
        waypoints: list[LatLon],
        costing_profile: str,
        departure_time: datetime | None,
    ) -> list[dict[str, Any]]:
        _ = waypoints, departure_time
        candidates = route_candidates(
            origin.lat,
            origin.lon,
            dest.lat,
            dest.lon,
            profile=costing_profile or "safest",
            k=3,
        )
        if candidates:
            return candidates
        # absolute fallback: straight-line single hop
        base = haversine_m((origin.lat, origin.lon), (dest.lat, dest.lon))
        return [
            {
                "id": "direct",
                "label": "Direct geodesic",
                "distance_m": base,
                "duration_s": base / 20.0,
                "segments": [
                    {
                        "name": "direct",
                        "distance_m": base,
                        "duration_s": base / 20.0,
                        "surface": "paved",
                        "weather": "clear",
                        "flood_exposure": 0.0,
                        "visibility_km": 12.0,
                        "wind_ms": 3.0,
                        "congestion": 0.1,
                        "incidents": [],
                    }
                ],
                "geometry": [
                    [origin.lat, origin.lon],
                    [dest.lat, dest.lon],
                ],
                "algorithm": "geodesic-fallback",
            }
        ]

    def matrix(
        self, sources: list[LatLon], targets: list[LatLon], profile: str
    ) -> dict[str, Any]:
        rows = []
        for s in sources:
            rows.append([haversine_m((s.lat, s.lon), (t.lat, t.lon)) for t in targets])
        return {"distances_m": rows, "profile": profile, "algorithm": "haversine"}
