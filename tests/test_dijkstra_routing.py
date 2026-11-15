from __future__ import annotations

from megmis.common.schemas import LatLon
from megmis.common.zw_graph import dijkstra, route_candidates, snap_to_node
from megmis.providers.mock_routing import MockRoutingProvider


def test_snap_and_dijkstra_harare_mutare():
    assert snap_to_node(-17.8252, 31.0335) == "harare"
    path = dijkstra("harare", "mutare", "safest")
    assert path is not None
    nodes, edges, weight = path
    assert nodes[0] == "harare"
    assert nodes[-1] == "mutare"
    assert edges and weight > 0


def test_fastest_and_safest_can_diverge():
    safe = dijkstra("harare", "bulawayo", "safest")
    fast = dijkstra("harare", "bulawayo", "fastest")
    assert safe and fast
    # both reach Bulawayo; weights differ by profile
    assert safe[0][-1] == "bulawayo"
    assert fast[0][-1] == "bulawayo"
    assert safe[2] != fast[2] or safe[0] != fast[0]


def test_route_candidates_include_geometry():
    # Bulawayo → Gweru
    cands = route_candidates(-20.1325, 28.6265, -19.45, 29.8167, profile="fastest", k=3)
    assert len(cands) >= 1
    assert cands[0]["algorithm"] == "dijkstra"
    assert len(cands[0]["geometry"]) >= 2
    assert "gweru" in cands[0]["node_path"]
    assert "bulawayo" in cands[0]["node_path"]


def test_mock_provider_uses_dijkstra():
    p = MockRoutingProvider()
    routes = p.route(
        LatLon(lat=-20.1325, lon=28.6265),
        LatLon(lat=-19.45, lon=29.8167),
        [],
        "safest",
        None,
    )
    assert routes
    assert routes[0].get("algorithm") == "dijkstra"
    assert routes[0].get("geometry")


def test_harare_to_nyamaropa_not_chitungwiza():
    """Regression: unknown/eastern places must not collapse to Harare→Chitungwiza."""
    from megmis.common.zimbabwe import lookup_place

    assert lookup_place("nyamaropa in nyanga zimbabwe") is not None
    o = lookup_place("harare")
    d = lookup_place("nyamaropa")
    assert o and d
    cands = route_candidates(o[0], o[1], d[0], d[1], profile="safest", k=3)
    assert cands
    path = " ".join(cands[0].get("node_path") or []).lower()
    assert "chitungwiza" not in path or "nyanga" in path or "nyamaropa" in path
    assert cands[0]["distance_m"] > 50_000  # intercity, not 30km Harare hop
