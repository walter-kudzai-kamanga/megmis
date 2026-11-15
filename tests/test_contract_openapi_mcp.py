from __future__ import annotations

from pathlib import Path

import yaml

from megmis.mcp.server import mcp


def test_openapi_paths_present(client):
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    for required in (
        "/api/v1/weather/current",
        "/api/v1/weather/risk",
        "/api/v1/routes/optimize",
        "/api/v1/roads/incidents",
        "/api/v1/journeys",
        "/api/v1/geo/geocode",
    ):
        assert required in paths


def test_docs_openapi_yaml_aligns():
    path = Path(__file__).resolve().parents[1] / "docs" / "api" / "openapi.yaml"
    doc = yaml.safe_load(path.read_text())
    assert doc["info"]["title"]
    paths = doc["paths"]
    assert any("optimize" in p for p in paths)
    for required in (
        "/keys",
        "/keys/{id}/rotate",
        "/risk/journey",
        "/traffic/congestion",
        "/console/health",
        "/webhooks",
    ):
        assert required in paths


def test_mcp_tools_registered():
    names = {t.name for t in mcp._tool_manager.list_tools()}
    required = {
        "get_current_weather",
        "analyze_weather_risk",
        "optimize_route",
        "get_road_incidents",
        "geocode",
        "assess_journey_risk",
        "get_traffic_congestion",
    }
    assert required.issubset(names)


def test_provenance_on_weather(client, headers_a):
    r = client.get("/api/v1/weather/current?name=Harare", headers=headers_a)
    body = r.json()
    prov = body["provenance"]
    assert prov["data_source"]
    assert prov["confidence"]
    assert prov["retrieved_at"]
