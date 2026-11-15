"""Zimbabwe intercity highway graph + Dijkstra for safest / fastest routing."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Any

from megmis.common.zimbabwe import KNOWN_PLACES


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371000.0
    lat1, lon1 = a
    lat2, lon2 = b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _lerp_path(
    a: tuple[float, float], b: tuple[float, float], via: tuple[float, float] | None = None, n: int = 8
) -> list[list[float]]:
    """Sample a simple curved polyline between two city nodes."""
    pts: list[list[float]] = []
    if via is None:
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        # slight offset so corridors don't stack perfectly
        via = (mid[0] + 0.08, mid[1] - 0.05)
    for i in range(n + 1):
        t = i / n
        # quadratic Bezier
        lat = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * via[0] + t**2 * b[0]
        lon = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * via[1] + t**2 * b[1]
        pts.append([round(lat, 5), round(lon, 5)])
    return pts


@dataclass(frozen=True)
class Edge:
    u: str
    v: str
    corridor: str
    distance_m: float
    speed_kmh: float
    surface: str
    safety_risk: float  # 0..1 higher = less safe
    weather_risk: float
    congestion: float
    via: tuple[float, float] | None = None


def node_coord(name: str) -> tuple[float, float]:
    c = KNOWN_PLACES.get(name) or KNOWN_PLACES.get(name.replace("_", " "))
    if not c:
        raise KeyError(name)
    return c


def _node_coord(name: str) -> tuple[float, float]:
    return node_coord(name)


def _build_edges() -> list[Edge]:
    """Undirected highway corridors (stored once; adjacency expands both ways)."""
    # distances approximate real corridor lengths
    raw = [
        ("harare", "chitungwiza", "Harare–Chitungwiza", 30_000, 60, "paved", 0.15, 0.1, 0.45, None),
        ("harare", "gweru", "A5 Harare–Gweru", 275_000, 85, "paved", 0.2, 0.15, 0.35, (-18.6, 30.2)),
        ("gweru", "bulawayo", "A5 Gweru–Bulawayo", 164_000, 90, "paved", 0.18, 0.12, 0.25, (-19.8, 29.2)),
        ("harare", "mutare", "A3 Harare–Mutare", 263_000, 80, "paved", 0.28, 0.35, 0.2, (-18.4, 31.9)),
        ("harare", "masvingo", "A4 Harare–Masvingo", 292_000, 85, "paved", 0.22, 0.2, 0.2, (-18.9, 30.9)),
        ("masvingo", "mutare", "A9 Masvingo–Mutare", 295_000, 70, "paved", 0.35, 0.4, 0.1, (-19.5, 31.8)),
        ("masvingo", "gweru", "A17 Masvingo–Gweru", 185_000, 75, "paved", 0.25, 0.25, 0.15, (-19.7, 30.3)),
        ("bulawayo", "victoria falls", "A8 Bulawayo–Vic Falls", 440_000, 90, "paved", 0.2, 0.15, 0.1, (-18.9, 27.2)),
        ("bulawayo", "gweru", "R2 Bulawayo–Gweru alt", 170_000, 70, "rough", 0.4, 0.3, 0.05, (-19.9, 29.1)),
        ("harare", "bulawayo", "A5 express (long)", 440_000, 95, "paved", 0.25, 0.2, 0.55, (-18.9, 29.8)),
        ("gweru", "mutare", "inland Gweru–Mutare", 340_000, 65, "rough", 0.45, 0.35, 0.08, (-19.2, 31.2)),
        ("masvingo", "bulawayo", "A6 Masvingo–Bulawayo", 280_000, 80, "paved", 0.3, 0.25, 0.12, (-20.1, 29.7)),
        # Eastern Highlands
        ("mutare", "nyanga", "A15 Mutare–Nyanga", 95_000, 55, "paved", 0.35, 0.45, 0.1, (-18.55, 32.72)),
        ("harare", "rusape", "A3 Harare–Rusape", 170_000, 80, "paved", 0.22, 0.25, 0.2, (-18.15, 31.6)),
        ("rusape", "mutare", "A3 Rusape–Mutare", 95_000, 75, "paved", 0.25, 0.3, 0.15, (-18.75, 32.4)),
        ("rusape", "nyanga", "Rusape–Nyanga", 110_000, 50, "rough", 0.4, 0.4, 0.08, (-18.3, 32.4)),
        ("nyanga", "nyamaropa", "Nyanga–Nyamaropa", 22_000, 40, "rough", 0.35, 0.4, 0.05, (-18.18, 32.8)),
        ("harare", "marondera", "A3 Harare–Marondera", 75_000, 85, "paved", 0.15, 0.15, 0.3, (-18.0, 31.3)),
        ("marondera", "rusape", "A3 Marondera–Rusape", 95_000, 80, "paved", 0.2, 0.2, 0.15, (-18.35, 31.85)),
    ]
    edges: list[Edge] = []
    for u, v, name, dist, spd, surf, safe, wx, cong, via in raw:
        edges.append(
            Edge(
                u=u,
                v=v,
                corridor=name,
                distance_m=float(dist),
                speed_kmh=float(spd),
                surface=surf,
                safety_risk=safe,
                weather_risk=wx,
                congestion=cong,
                via=via,
            )
        )
    return edges


_EDGES = _build_edges()
_NODES = sorted({e.u for e in _EDGES} | {e.v for e in _EDGES})


def graph_nodes() -> list[str]:
    return list(_NODES)


def snap_to_node(lat: float, lon: float) -> str:
    best = _NODES[0]
    best_d = float("inf")
    for n in _NODES:
        d = haversine_m((lat, lon), _node_coord(n))
        if d < best_d:
            best_d = d
            best = n
    return best


def _edge_weight(edge: Edge, profile: str) -> float:
    hours = (edge.distance_m / 1000.0) / max(5.0, edge.speed_kmh * (1.0 - 0.5 * edge.congestion))
    surf = 0.0 if edge.surface == "paved" else 0.35 if edge.surface == "rough" else 0.6
    if profile == "fastest":
        return hours * (1.0 + 0.15 * edge.congestion)
    if profile == "fuel":
        return (edge.distance_m / 1000.0) * (1.0 + 0.4 * surf + 0.2 * edge.congestion)
    if profile == "cheapest":
        return (edge.distance_m / 1000.0) * (1.0 + 0.3 * surf) + hours * 0.5
    # safest (default): heavily penalise risk / weather / rough surface
    return hours * (
        1.0
        + 2.2 * edge.safety_risk
        + 1.8 * edge.weather_risk
        + 1.2 * surf
        + 0.4 * edge.congestion
    )


def _adjacency() -> dict[str, list[tuple[str, Edge]]]:
    adj: dict[str, list[tuple[str, Edge]]] = {n: [] for n in _NODES}
    for e in _EDGES:
        adj[e.u].append((e.v, e))
        # undirected mirror
        mirror = Edge(
            u=e.v,
            v=e.u,
            corridor=e.corridor,
            distance_m=e.distance_m,
            speed_kmh=e.speed_kmh,
            surface=e.surface,
            safety_risk=e.safety_risk,
            weather_risk=e.weather_risk,
            congestion=e.congestion,
            via=e.via,
        )
        adj[e.v].append((e.u, mirror))
    return adj


def dijkstra(
    origin: str,
    destination: str,
    profile: str = "safest",
    *,
    blocked: set[tuple[str, str]] | None = None,
) -> tuple[list[str], list[Edge], float] | None:
    """
    Classic Dijkstra shortest path on the Zimbabwe highway graph.
    Returns (node_path, edge_path, total_weight) or None if unreachable.
    """
    if origin not in _NODES or destination not in _NODES:
        return None
    blocked = blocked or set()
    adj = _adjacency()
    dist: dict[str, float] = {n: float("inf") for n in _NODES}
    prev: dict[str, tuple[str, Edge] | None] = {n: None for n in _NODES}
    dist[origin] = 0.0
    pq: list[tuple[float, str]] = [(0.0, origin)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        if u == destination:
            break
        for v, edge in adj[u]:
            key = (min(u, v), max(u, v))
            if key in blocked:
                continue
            w = _edge_weight(edge, profile)
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = (u, edge)
                heapq.heappush(pq, (nd, v))
    if dist[destination] == float("inf"):
        return None
    nodes: list[str] = []
    edges: list[Edge] = []
    cur = destination
    while cur != origin:
        step = prev[cur]
        if step is None:
            return None
        p, edge = step
        nodes.append(cur)
        edges.append(edge)
        cur = p
    nodes.append(origin)
    nodes.reverse()
    edges.reverse()
    return nodes, edges, dist[destination]


def _path_geometry(nodes: list[str], edges: list[Edge]) -> list[list[float]]:
    geom: list[list[float]] = []
    for i, edge in enumerate(edges):
        a = _node_coord(nodes[i])
        b = _node_coord(nodes[i + 1])
        seg = _lerp_path(a, b, edge.via)
        if geom:
            seg = seg[1:]  # avoid duplicate joint
        geom.extend(seg)
    if not geom and nodes:
        c = _node_coord(nodes[0])
        geom = [[c[0], c[1]]]
    return geom


def _candidate_from_path(
    nodes: list[str],
    edges: list[Edge],
    *,
    path_id: str,
    label: str,
) -> dict[str, Any]:
    distance_m = sum(e.distance_m for e in edges)
    duration_s = 0.0
    segments = []
    for e in edges:
        hours = (e.distance_m / 1000.0) / max(5.0, e.speed_kmh * (1.0 - 0.5 * e.congestion))
        duration_s += hours * 3600.0
        incidents = []
        if e.safety_risk >= 0.4:
            incidents.append(
                {
                    "type": "damaged_road",
                    "severity": 3,
                    "confidence": min(0.9, 0.5 + e.safety_risk),
                    "age_hours": 4,
                    "verified_closure": False,
                }
            )
        if e.weather_risk >= 0.35:
            incidents.append(
                {
                    "type": "flood",
                    "severity": 4,
                    "confidence": min(0.9, e.weather_risk + 0.3),
                    "age_hours": 3,
                    "verified_closure": False,
                }
            )
        weather = "heavy_rain" if e.weather_risk >= 0.35 else "clear"
        segments.append(
            {
                "name": e.corridor,
                "distance_m": e.distance_m,
                "duration_s": hours * 3600.0,
                "surface": e.surface,
                "weather": weather,
                "flood_exposure": e.weather_risk,
                "visibility_km": 4.0 if weather == "heavy_rain" else 12.0,
                "wind_ms": 7.0 if weather == "heavy_rain" else 3.0,
                "congestion": e.congestion,
                "incidents": incidents,
            }
        )
    via = " → ".join(n.replace("_", " ").title() for n in nodes)
    return {
        "id": path_id,
        "label": label or via,
        "distance_m": distance_m,
        "duration_s": duration_s,
        "segments": segments,
        "geometry": _path_geometry(nodes, edges),
        "node_path": nodes,
        "algorithm": "dijkstra",
        "via": via,
    }


def route_candidates(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    profile: str = "safest",
    *,
    k: int = 3,
) -> list[dict[str, Any]]:
    """
    Snap O/D to graph nodes, run Dijkstra, then produce up to k alternatives
    by blocking edges on previously found paths (Yen's-style edge blocking).
    """
    o = snap_to_node(origin_lat, origin_lon)
    d = snap_to_node(dest_lat, dest_lon)
    # If lat/lon are far apart but snap to same hub, keep geodesic fallback —
    # never invent a random neighbour (that caused Harare→Chitungwiza hallucinations).
    if o == d:
        sep = haversine_m((origin_lat, origin_lon), (dest_lat, dest_lon))
        if sep < 2500:
            return []  # truly the same place — caller should refuse
        # Off-graph destination near a hub: return a direct geodesic leg with map geometry
        hours = (sep / 1000.0) / 50.0
        return [
            {
                "id": "geodesic-local",
                "label": f"Local access near {o.replace('_', ' ').title()}",
                "distance_m": sep,
                "duration_s": hours * 3600.0,
                "segments": [
                    {
                        "name": "local access",
                        "distance_m": sep,
                        "duration_s": hours * 3600.0,
                        "surface": "rough",
                        "weather": "clear",
                        "flood_exposure": 0.1,
                        "visibility_km": 10.0,
                        "wind_ms": 3.0,
                        "congestion": 0.05,
                        "incidents": [],
                    }
                ],
                "geometry": [
                    [round(origin_lat, 5), round(origin_lon, 5)],
                    [round(dest_lat, 5), round(dest_lon, 5)],
                ],
                "node_path": [o],
                "algorithm": "geodesic",
                "via": f"{o.replace('_', ' ').title()} local access",
            }
        ]

    found: list[dict[str, Any]] = []
    blocked: set[tuple[str, str]] = set()
    profiles_cycle = [profile, "fastest" if profile != "fastest" else "safest", "fuel"]

    for i in range(max(1, k)):
        use_profile = profiles_cycle[i % len(profiles_cycle)] if i > 0 else profile
        result = dijkstra(o, d, use_profile, blocked=blocked)
        if result is None:
            break
        nodes, edges, _w = result
        label = f"Dijkstra {use_profile}: " + " → ".join(n.replace("_", " ").title() for n in nodes)
        cand = _candidate_from_path(nodes, edges, path_id=f"dij-{i+1}", label=label)
        cand["profile_used"] = use_profile
        # skip duplicate geometries
        sig = tuple(nodes)
        if any(tuple(c.get("node_path") or []) == sig for c in found):
            # block heaviest edge and retry
            if edges:
                e = max(edges, key=lambda x: x.distance_m)
                blocked.add((min(e.u, e.v), max(e.u, e.v)))
            continue
        found.append(cand)
        # block longest edge of this path to force divergence next round
        if edges:
            e = max(edges, key=lambda x: _edge_weight(x, profile))
            blocked.add((min(e.u, e.v), max(e.u, e.v)))

    return found
