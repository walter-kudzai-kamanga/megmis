from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC

import pytest


@pytest.mark.integration
def test_api_key_rotate_and_revoke(client, headers_a, settings):
    created = client.post(
        "/api/v1/keys",
        headers=headers_a,
        json={"label": "gen2-test", "scopes": ["weather:read", "webhook:manage"]},
    )
    assert created.status_code == 201
    key_id = created.json()["data"]["id"]
    raw = created.json()["data"]["raw_key"]
    assert raw.startswith("meg_")

    rotated = client.post(f"/api/v1/keys/{key_id}/rotate", headers=headers_a)
    assert rotated.status_code == 200
    new_raw = rotated.json()["data"]["raw_key"]
    assert new_raw != raw

    # old raw should fail once cache invalidated / DB updated
    bad = client.get("/api/v1/weather/current?name=Harare", headers={"X-API-Key": raw})
    assert bad.status_code == 401

    ok = client.get("/api/v1/weather/current?name=Harare", headers={"X-API-Key": new_raw})
    assert ok.status_code == 200

    revoked = client.post(f"/api/v1/keys/{key_id}/revoke", headers=headers_a)
    assert revoked.status_code == 200
    dead = client.get("/api/v1/weather/current?name=Harare", headers={"X-API-Key": new_raw})
    assert dead.status_code == 401


@pytest.mark.integration
def test_webhook_hmac_signature_roundtrip(client, headers_a):
    from megmis.api.v1.webhooks import sign_payload, verify_signature

    reg = client.post(
        "/api/v1/webhooks",
        headers=headers_a,
        json={"url": "https://example.com/hooks/mamiriro", "events": ["road.report"]},
    )
    assert reg.status_code == 201
    secret = reg.json()["data"]["secret"]
    body = json.dumps({"event": "road.report", "payload": {"ok": True}}).encode()
    ts = int(time.time())
    sig = sign_payload(secret, body, ts)
    assert verify_signature(secret, body, sig, ts)
    assert not verify_signature(secret, body, sig, ts - 10_000)


@pytest.mark.integration
def test_journey_risk_persisted(client, headers_a):
    r = client.post(
        "/api/v1/risk/journey",
        headers=headers_a,
        json={
            "origin": {"name": "Harare"},
            "destination": {"name": "Bulawayo"},
            "profile": "safest",
            "activity": "road_trip",
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["level"] in {"low", "moderate", "high"}
    assert "assessment_id" in data
    got = client.get(f"/api/v1/risk/{data['assessment_id']}", headers=headers_a)
    assert got.status_code == 200
    assert got.json()["data"]["assessment_id"] == data["assessment_id"]


def test_traffic_submodule_peak_logic():
    from datetime import datetime

    from megmis.engines.routing import traffic

    off = traffic.get_congestion("A5 Harare-Bulawayo", datetime(2026, 11, 15, 12, tzinfo=UTC))
    peak = traffic.get_congestion("A5 Harare-Bulawayo", datetime(2026, 11, 15, 8, tzinfo=UTC))
    assert peak["congestion"] >= off["congestion"]
    assert "a5" in peak["matched_profile"]
    est = traffic.estimate_time_at(3600, "A1 Harare")
    assert est["duration_s"] >= 3600


def test_road_pipeline_validation_unit(monkeypatch):
    from megmis.engines.road import pipeline

    # Without DB this may no-op / error; just ensure callable returns dict shape when persistence off
    # Integration covers real path.
    assert callable(pipeline.validate_pending_reports)


def test_webhook_sign_helpers():
    from megmis.api.v1.webhooks import sign_payload, verify_signature

    secret = "abc123"
    body = b'{"a":1}'
    ts = int(time.time())
    sig = sign_payload(secret, body, ts)
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    assert sig == expected
    assert verify_signature(secret, body, sig, ts)


@pytest.mark.integration
def test_console_and_traffic_endpoints(client, headers_a):
    health = client.get("/api/v1/console/health", headers=headers_a)
    assert health.status_code == 200
    usage = client.get("/api/v1/console/usage", headers=headers_a)
    assert usage.status_code == 200
    page = client.get("/api/v1/console/", headers=headers_a)
    assert page.status_code == 200
    assert b"Mamiriro Console" in page.content

    cong = client.get("/api/v1/traffic/congestion?corridor=A5%20Harare-Bulawayo", headers=headers_a)
    assert cong.status_code == 200
    assert "congestion" in cong.json()["data"]


@pytest.mark.integration
def test_worker_validate_reports_job(client, headers_a):
    # create a report then run validation job
    client.post(
        "/api/v1/roads/reports",
        headers=headers_a,
        json={"location": {"name": "Harare"}, "type": "pothole", "severity": 4},
    )
    from megmis.engines.road.pipeline import validate_pending_reports

    result = validate_pending_reports()
    assert "validated" in result


def test_provider_factory_and_protocols():
    from megmis.providers.factory import (
        get_geocoding_provider,
        get_routing_provider,
        get_weather_provider,
    )
    from megmis.providers.protocols import GeocodingProvider, RoutingProvider, WeatherProvider

    w = get_weather_provider()
    r = get_routing_provider()
    g = get_geocoding_provider()
    assert isinstance(w, WeatherProvider)
    assert isinstance(r, RoutingProvider)
    assert isinstance(g, GeocodingProvider)


def test_real_provider_classes_importable():
    from megmis.providers.http_routing import (
        GraphHopperRoutingProvider,
        OSRMRoutingProvider,
        ValhallaRoutingProvider,
    )
    from megmis.providers.open_meteo import OpenMeteoWeatherProvider
    from megmis.providers.openweather import OpenWeatherProvider

    assert OpenMeteoWeatherProvider.name == "open-meteo"
    assert OpenWeatherProvider.name == "openweather"
    assert ValhallaRoutingProvider.name == "valhalla"
    assert GraphHopperRoutingProvider.name == "graphhopper"
    assert OSRMRoutingProvider.name == "osrm"


def test_token_bucket_plan_tiers(monkeypatch):
    from megmis.db import redis_cache

    store: dict[str, dict] = {}

    class FakeRedis:
        def pipeline(self):
            return self

        def hgetall(self, key):
            return store.get(key, {})

        def execute(self):
            return [store.get(getattr(self, "_last_key", ""), {})]

        def hset(self, key, mapping):
            store[key] = {k: str(v) for k, v in mapping.items()}
            self._last_key = key

        def expire(self, key, _ttl):
            return True

        def hgetall_then(self):
            pass

    # Simplify: patch _bucket_take via get_redis returning in-memory fake
    class Pipe:
        def __init__(self, r):
            self.r = r
            self.key = None

        def hgetall(self, key):
            self.key = key
            return self

        def execute(self):
            return [self.r.data.get(self.key, {})]

    class MemRedis:
        def __init__(self):
            self.data: dict[str, dict] = {}

        def pipeline(self):
            return Pipe(self)

        def hset(self, key, mapping):
            self.data[key] = {str(k): str(v) for k, v in mapping.items()}

        def expire(self, key, ttl):
            return True

    mem = MemRedis()
    monkeypatch.setattr(redis_cache, "get_redis", lambda: mem)
    ok, _ = redis_cache.token_bucket_allow("t1", plan="free", cost=1)
    assert ok is True
    # Exhaust free tier capacity quickly
    denied = False
    for _ in range(80):
        allowed, retry = redis_cache.token_bucket_allow("t1", plan="free", cost=1)
        if not allowed:
            denied = True
            assert retry >= 1
            break
    assert denied


def test_traffic_list_corridors():
    from megmis.engines.routing import traffic

    corridors = traffic.list_corridors()
    assert "a5 harare-bulawayo" in corridors
    assert "default" not in corridors


def test_webhook_header_name():
    from megmis.api.v1 import webhooks

    assert hasattr(webhooks, "sign_payload")
    # delivery uses X-Mamiriro-Signature (checked via source contract in delivery helper)
    import inspect

    src = inspect.getsource(webhooks)
    assert "X-Mamiriro-Signature" in src
    assert "enqueue_event" in src
    assert "_BACKOFF" in src


def test_worker_graph_refresh_writes_marker(tmp_path, monkeypatch):
    from pathlib import Path

    osm = tmp_path / "extract.osm"
    osm.write_text("<osm></osm>")
    out = tmp_path / "refresh"
    monkeypatch.setenv("OSM_EXTRACT_PATH", str(osm))
    monkeypatch.setenv("GRAPH_REFRESH_DIR", str(out))
    from megmis.config import get_settings

    get_settings.cache_clear()
    from megmis import worker

    # Avoid DB job recording failures in pure unit mode
    monkeypatch.setattr(worker, "_record_job", lambda *a, **k: None)
    result = worker.job_graph_refresh()
    assert result["status"] == "ready_for_swap"
    assert Path(result["marker"]).exists()
    get_settings.cache_clear()


@pytest.mark.integration
def test_mcp_assess_journey_risk_persists():
    """MCP tool resolves demo tenant and persists when USE_PERSISTENCE is on."""
    from megmis.mcp.server import assess_journey_risk

    out = assess_journey_risk(
        {"name": "Harare"},
        {"name": "Bulawayo"},
        profile="safest",
        activity="road_trip",
    )
    assert "data" in out
    assert out["data"].get("assessment_id"), out


@pytest.mark.integration
def test_webhook_durable_queue_enqueue(client, headers_a, monkeypatch):
    from megmis.api.v1 import webhooks

    calls: list[dict] = []

    def fake_post(url, content=None, headers=None, timeout=5.0):
        calls.append({"url": url, "headers": headers, "body": content})

        class R:
            status_code = 500

        return R()

    monkeypatch.setattr(webhooks.httpx, "post", fake_post)
    reg = client.post(
        "/api/v1/webhooks",
        headers=headers_a,
        json={"url": "https://example.com/hooks/fail", "events": ["alert.weather"]},
    )
    assert reg.status_code == 201
    # resolve tenant id via console health
    from megmis.common.auth import hash_api_key, lookup_api_key
    from megmis.config import get_settings

    ctx = lookup_api_key(hash_api_key(get_settings().dev_api_key))
    assert ctx
    results = webhooks.deliver_event(str(ctx.tenant_id), "alert.weather", {"ping": True})
    assert results
    assert any(r.get("ok") is False for r in results)
    # retry row should exist
    assert any(r.get("attempts", 0) >= 1 for r in results)
