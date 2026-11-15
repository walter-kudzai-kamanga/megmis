from __future__ import annotations

import pytest

from megmis.common.pii import redact_transcript, rotating_pseudonym
from megmis.common.secrets import EnvSecretManager, get_secret_manager
from megmis.engines.routing import calibration, cost_model
from megmis.providers.orchestrator import FailoverChain, ProviderOrchestrator, reset_orchestrator
from megmis.storage.object_store import LocalObjectStore, reset_object_store


def test_pii_redaction():
    text = "Call me on +263771234567 or mail a@b.co.zw about 12345678"
    out = redact_transcript(text)
    assert "+263771234567" not in out
    assert "a@b.co.zw" not in out
    assert rotating_pseudonym("x") == rotating_pseudonym("x")


def test_secret_manager_env(monkeypatch):
    get_secret_manager.cache_clear()
    monkeypatch.setenv("SECRET_MANAGER", "env")
    monkeypatch.setenv("OPENWEATHER_KEY", "test-key-123")
    from megmis.config import get_settings

    get_settings.cache_clear()
    sm = EnvSecretManager()
    assert sm.get("OPENWEATHER_KEY") == "test-key-123"
    get_secret_manager.cache_clear()
    get_settings.cache_clear()


def test_failover_health_gated():
    reset_orchestrator()
    orch = ProviderOrchestrator()
    orch.configure_chain(FailoverChain("weather", "primary", ["fallback"], failure_threshold=2))
    orch.register_builder("primary", lambda: "P")
    orch.register_builder("fallback", lambda: "F")
    assert orch.get_provider("weather") == "P"
    orch.record_failure("weather", "primary", "boom1")
    assert orch.active("weather") == "primary"
    orch.record_failure("weather", "primary", "boom2")
    assert orch.get_provider("weather") == "F"
    snap = orch.health_snapshot()
    assert snap["providers"]["primary"]["healthy"] is False
    reset_orchestrator()


def test_gps_calibration_updates_weights():
    # reset safest weights baseline
    cost_model.WEIGHT_PROFILES["safest"] = {
        "w_time": 0.4,
        "w_dist": 0.05,
        "w_surface": 0.6,
        "w_weather": 0.8,
        "w_incident": 0.9,
    }
    tid = "00000000-0000-0000-0000-000000000099"
    for _i in range(4):
        calibration.ingest_trace(
            tid,
            points=[
                {"lat": -17.8, "lon": 31.0, "speed_mps": 10},
                {"lat": -17.9, "lon": 31.2, "speed_mps": 9},
                {"lat": -18.0, "lon": 31.4, "speed_mps": 8},
            ],
            profile="safest",
        )
    before = dict(cost_model.WEIGHT_PROFILES["safest"])
    result = calibration.calibrate_weights(tid, profile="safest", min_traces=3)
    after = cost_model.WEIGHT_PROFILES["safest"]
    assert result["trace_count"] >= 3
    assert after["w_time"] >= before["w_time"]  # slow traces bump time weight


def test_local_object_store_retention(tmp_path):
    reset_object_store()
    store = LocalObjectStore(root=str(tmp_path))
    obj = store.put(b"hello", prefix="evidence", retention_days=0)
    assert obj.bytes == 5
    # force expiry in the past by rewriting meta
    import json
    from datetime import UTC, datetime, timedelta
    from pathlib import Path

    meta_path = Path(str(tmp_path / obj.key) + ".meta.json")
    meta = json.loads(meta_path.read_text())
    meta["expires_at"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    meta_path.write_text(json.dumps(meta))
    purged = store.purge_expired()
    assert purged["removed"] >= 1
    reset_object_store()


def test_pack_service_lists_and_runs_insurance():
    from megmis.common.schemas import LocationInput
    from megmis.engines.packs import PackService

    svc = PackService()
    packs = svc.list_packs()
    assert any(p["id"] == "insurance.corridor" for p in packs)
    env = svc.run_pack(
        "insurance.corridor",
        origin=LocationInput(name="Harare"),
        destination=LocationInput(name="Mutare"),
        tenant_id=None,
    )
    assert env.data["summary"]["risk_level"]
    assert "journey_risk" in env.data["sections"]


@pytest.mark.integration
def test_gen4_api_surfaces(client, headers_a):
    packs = client.get("/api/v1/packs", headers=headers_a)
    assert packs.status_code == 200
    assert packs.json()["data"]["packs"]

    run = client.post(
        "/api/v1/packs/govtech.emergency/run",
        headers=headers_a,
        json={"location": {"name": "Harare"}},
    )
    assert run.status_code == 200

    health = client.get("/api/v1/ops/providers", headers=headers_a)
    assert health.status_code == 200
    assert "active" in health.json()["data"]

    # ingest 3 traces + calibrate
    pts = {
        "points": [
            {"lat": -17.8, "lon": 31.0, "speed_mps": 11},
            {"lat": -17.85, "lon": 31.1, "speed_mps": 10},
            {"lat": -17.9, "lon": 31.2, "speed_mps": 9},
        ],
        "profile": "safest",
    }
    for _ in range(3):
        r = client.post("/api/v1/ops/traces", headers=headers_a, json=pts)
        assert r.status_code == 201
    cal = client.post(
        "/api/v1/ops/calibrate",
        headers=headers_a,
        json={"profile": "safest", "min_traces": 3},
    )
    assert cal.status_code == 200
    assert cal.json()["data"]["weights_after"]

    demo = client.post("/api/v1/ops/storage/put-demo", headers=headers_a)
    assert demo.status_code == 200
    assert demo.json()["data"]["uri"]

    metrics = client.get("/api/v1/metrics")
    assert metrics.status_code == 200
    assert b"megmis_" in metrics.content

    root_metrics = client.get("/metrics")
    assert root_metrics.status_code == 200
