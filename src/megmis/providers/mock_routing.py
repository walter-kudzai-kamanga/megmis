"""Hybrid routing: Dijkstra on Zimbabwe graph + OSRM fallback for any lat/lon."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from megmis.common.schemas import LatLon
from megmis.common.zw_graph import haversine_m, node_coord, route_candidates, snap_to_node


class MockRoutingProvider:
    """
    Primary: Dijkstra over Zimbabwe highway hubs with access legs to true coords.
    Fallback: public OSRM when hubs are far from the requested points (any place).
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
        profile = costing_profile or "safest"
        candidates = route_candidates(
            origin.lat,
            origin.lon,
            dest.lat,
            dest.lon,
            profile=profile,
            k=3,
        )
        # Attach true endpoints onto geometry so the map shows the real places
        for c in candidates:
            geom = list(c.get("geometry") or [])
            start = [round(origin.lat, 5), round(origin.lon, 5)]
            end = [round(dest.lat, 5), round(dest.lon, 5)]
            if not geom or geom[0] != start:
                geom = [start] + geom
            if geom[-1] != end:
                geom = geom + [end]
            c["geometry"] = geom

        # If snapped hubs are far from the requested points, also try OSRM
        try:
            o_hub = snap_to_node(origin.lat, origin.lon)
            d_hub = snap_to_node(dest.lat, dest.lon)
            o_gap = haversine_m((origin.lat, origin.lon), node_coord(o_hub))
            d_gap = haversine_m((dest.lat, dest.lon), node_coord(d_hub))
            need_osrm = o_gap > 80_000 or d_gap > 80_000 or not candidates
        except Exception:
            need_osrm = not candidates

        if need_osrm:
            try:
                from megmis.providers.http_routing import OSRMRoutingProvider

                osrm = OSRMRoutingProvider().route(origin, dest, [], profile, departure_time)
                for c in osrm:
                    c.setdefault("algorithm", "osrm")
                # Prefer OSRM when local graph is a poor fit; keep Dijkstra as extras
                candidates = osrm + candidates
            except Exception:
                if not candidates:
                    base = haversine_m((origin.lat, origin.lon), (dest.lat, dest.lon))
                    candidates = [
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

        return candidates[:5]

    def matrix(
        self, sources: list[LatLon], targets: list[LatLon], profile: str
    ) -> dict[str, Any]:
        rows = []
        for s in sources:
            rows.append([haversine_m((s.lat, s.lon), (t.lat, t.lon)) for t in targets])
        return {"distances_m": rows, "profile": profile, "algorithm": "haversine"}
