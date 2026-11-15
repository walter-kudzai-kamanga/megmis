"""Functional MCP audits: tool calls, auth, errors, HTTP transport, failover."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from megmis.common.auth import TenantContext, seed_dev_key
from megmis.common.tenant_ctx import reset_tenant_context, set_tenant_context
from megmis.config import get_settings
from megmis.mcp.runtime import (
    MCP_SCHEMA_VERSION,
    MCP_SERVER_NAME,
    parse_tool_error,
    reset_mcp_services,
    server_card,
)
from megmis.mcp.server import mcp
from megmis.providers.orchestrator import reset_orchestrator


async def _call(name: str, arguments: dict):
    return await mcp.call_tool(name, arguments)


def _text(result) -> str:
    parts = []
    for c in getattr(result, "content", None) or []:
        if hasattr(c, "text"):
            parts.append(c.text)
    return "\n".join(parts)


def _body(result) -> dict | None:
    sc = getattr(result, "structuredContent", None)
    if isinstance(sc, dict):
        return sc
    text = _text(result)
    try:
        return json.loads(text)
    except Exception:
        return None


def _error_payload(exc: ToolError) -> dict | None:
    return parse_tool_error(str(exc))


@pytest.fixture(autouse=True)
def _mcp_isolation(monkeypatch):
    monkeypatch.setenv("USE_PERSISTENCE", "false")
    monkeypatch.setenv("GEOCODE_PROVIDER", "mock")
    monkeypatch.setenv("WEATHER_PROVIDER", "mock")
    monkeypatch.setenv("ROUTING_PROVIDER", "mock")
    monkeypatch.setenv("AUTH_DISABLED", "false")
    get_settings.cache_clear()
    reset_orchestrator()
    from megmis.providers.factory import clear_provider_caches

    clear_provider_caches()
    reset_mcp_services()
    seed_dev_key(get_settings())
    token = set_tenant_context(None)
    yield
    reset_tenant_context(token)
    reset_mcp_services()
    get_settings.cache_clear()
    reset_orchestrator()


@pytest.mark.asyncio
async def test_read_tool_happy_path_includes_meta():
    res = await _call("get_current_weather", {"location": {"name": "Harare"}})
    assert not getattr(res, "isError", False)
    body = _body(res)
    assert body and "data" in body and "provenance" in body
    assert body["meta"]["x-mcp-version"] == MCP_SCHEMA_VERSION
    assert body["meta"]["server"] == MCP_SERVER_NAME


@pytest.mark.asyncio
async def test_app_error_is_structured_json():
    with pytest.raises(ToolError) as ei:
        await _call("get_current_weather", {"location": {}})
    payload = _error_payload(ei.value)
    assert payload is not None
    assert payload["code"] == "INVALID_LOCATION"
    assert payload["request_id"]


@pytest.mark.asyncio
async def test_forecast_days_validated():
    with pytest.raises(ToolError) as ei:
        await _call("get_forecast", {"location": {"name": "Harare"}, "days": 99})
    payload = _error_payload(ei.value)
    assert payload and payload["code"] == "INVALID_PARAMS"


@pytest.mark.asyncio
async def test_mutating_tool_requires_auth():
    with pytest.raises(ToolError) as ei:
        await _call(
            "report_road_condition",
            {"location": {"name": "Harare"}, "type": "pothole", "severity": 2},
        )
    payload = _error_payload(ei.value)
    assert payload and payload["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_mutating_tool_enforces_scope():
    settings = get_settings()
    # Bind a tenant that lacks road:write
    limited = TenantContext(
        tenant_id=seed_dev_key(settings).tenant_id,
        slug="limited",
        plan="free",
        scopes=["weather:read"],
        api_key_prefix="limited",
    )
    token = set_tenant_context(limited)
    try:
        with pytest.raises(ToolError) as ei:
            await _call(
                "report_road_condition",
                {"location": {"name": "Harare"}, "type": "pothole", "severity": 2},
            )
        payload = _error_payload(ei.value)
        assert payload and payload["code"] == "FORBIDDEN"
        assert "road:write" in payload["message"]
    finally:
        reset_tenant_context(token)


@pytest.mark.asyncio
async def test_mutating_tool_with_api_key():
    settings = get_settings()
    res = await _call(
        "report_road_condition",
        {
            "location": {"name": "Harare"},
            "type": "pothole",
            "severity": 2,
            "api_key": settings.dev_api_key,
        },
    )
    assert not getattr(res, "isError", False)
    body = _body(res)
    assert body and body["data"]["report_id"]
    assert body["meta"]["x-mcp-version"] == MCP_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_create_journey_and_reroute():
    settings = get_settings()
    key = settings.dev_api_key
    opt = await _call(
        "optimize_route",
        {"origin": {"name": "Harare"}, "destination": {"name": "Bulawayo"}},
    )
    assert not getattr(opt, "isError", False)
    route_id = _body(opt)["data"]["route_id"]

    created = await _call("create_journey", {"route_id": route_id, "api_key": key})
    assert not getattr(created, "isError", False)
    journey_id = _body(created)["data"]["id"]

    rerouted = await _call(
        "reroute",
        {
            "journey_id": journey_id,
            "current_position": {"lat": -18.0, "lon": 30.5},
            "api_key": key,
        },
    )
    assert not getattr(rerouted, "isError", False)
    assert "alternatives" in _body(rerouted)["data"]


@pytest.mark.asyncio
async def test_reroute_missing_journey_structured_error():
    settings = get_settings()
    with pytest.raises(ToolError) as ei:
        await _call(
            "reroute",
            {
                "journey_id": "missing",
                "current_position": {"lat": -18.0, "lon": 30.5},
                "api_key": settings.dev_api_key,
            },
        )
    payload = _error_payload(ei.value)
    assert payload and payload["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_traffic_envelope_has_provenance():
    res = await _call("get_traffic_congestion", {"corridor": "Harare-Bulawayo"})
    assert not getattr(res, "isError", False)
    body = _body(res)
    assert body and "provenance" in body and "request_id" in body and "meta" in body


@pytest.mark.asyncio
async def test_tool_annotations_present():
    tools = {t.name: t for t in await mcp.list_tools()}
    assert tools["get_current_weather"].annotations.read_only_hint is True
    assert tools["report_road_condition"].annotations.read_only_hint is False
    assert "create_journey" in tools


@pytest.mark.asyncio
async def test_resource_and_prompt_contract():
    templates = await mcp.list_resource_templates()
    uris = {
        getattr(t, "uriTemplate", None) or getattr(t, "uri_template", None) for t in templates
    }
    assert "weather://historical/{location}" in uris
    prompts = {p.name for p in await mcp.list_prompts()}
    assert "assess_journey_risk" in prompts


@pytest.mark.asyncio
async def test_geocode_failover_to_mock(monkeypatch):
    """Nominatim ProviderError should fall through to mock via orchestrator.invoke."""
    monkeypatch.setenv("GEOCODE_PROVIDER", "nominatim")
    monkeypatch.setenv("GEOCODE_FAILOVER", "mock")
    get_settings.cache_clear()
    reset_orchestrator()
    reset_mcp_services()
    from megmis.providers.factory import clear_provider_caches

    clear_provider_caches()

    from megmis.common.errors import ProviderError
    from megmis.providers import nominatim_geocoding as nom

    def boom_reverse(self, lat, lon):
        raise ProviderError("simulated network", retryable=True)

    monkeypatch.setattr(nom.NominatimGeocodingProvider, "reverse", boom_reverse)

    from megmis.engines.geo.service import GeoService

    env = GeoService().reverse(-17.8252, 31.0335)
    assert env.data["address"]
    assert "mock" in env.provenance.data_source or "Zimbabwe" in env.data["address"]


def test_http_initialize_and_call(client, headers_a):
    headers = {
        **headers_a,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    init = client.post(
        "/mcp/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        },
        headers=headers,
    )
    assert init.status_code == 200, init.text
    assert "result" in init.json() or "capabilities" in init.text

    listed = client.post(
        "/mcp/",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        headers=headers,
    )
    assert listed.status_code == 200
    payload = listed.json()
    tools = payload.get("result", {}).get("tools") or []
    names = {t["name"] for t in tools}
    assert "create_journey" in names
    assert "get_current_weather" in names


def test_http_tool_error_is_error_flag(client, headers_a):
    headers = {
        **headers_a,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    client.post(
        "/mcp/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        },
        headers=headers,
    )
    err = client.post(
        "/mcp/",
        json={
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "get_forecast", "arguments": {"location": {"name": "Harare"}, "days": 99}},
        },
        headers=headers,
    )
    assert err.status_code == 200
    body = err.json()
    result = body.get("result") or {}
    assert result.get("isError") is True
    text = " ".join(
        c.get("text", "") for c in (result.get("content") or []) if isinstance(c, dict)
    )
    assert "INVALID_PARAMS" in text


def test_well_known_mcp_discovery(client):
    card = client.get("/.well-known/mcp.json")
    assert card.status_code == 200
    data = card.json()
    assert data["name"] == MCP_SERVER_NAME
    assert data["transports"]

    catalog = client.get("/.well-known/ai-catalog.json")
    assert catalog.status_code == 200
    assert catalog.json()["servers"][0]["name"] == MCP_SERVER_NAME


def test_server_json_manifest_aligns():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "server.json").read_text())
    assert manifest["name"] == MCP_SERVER_NAME
    assert manifest["version"] == server_card()["version"]
    pkg = manifest["packages"][0]
    assert pkg["registryType"] == "pypi"
    assert pkg["identifier"] == "megmis"
    assert pkg["transport"]["type"] == "stdio"
    readme = (root / "README.md").read_text()
    assert f"mcp-name: {MCP_SERVER_NAME}" in readme
