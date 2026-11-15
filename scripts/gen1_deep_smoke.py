#!/usr/bin/env python3
"""Deep Gen 1 smoke against a running API + PostGIS + Redis."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from redis import Redis
from sqlalchemy import create_engine, text

BASE = os.environ.get("MEGMIS_BASE_URL", "http://127.0.0.1:8000")
KEY_A = os.environ.get("DEV_API_KEY", "meg_local_devkey00000000000000000001")
KEY_B = os.environ.get("DEV_API_KEY_B", "meg_local_tenantb00000000000000000002")
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://megmis:megmis@localhost:5433/megmis"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

failures: list[str] = []
passes: list[str] = []


def ok(name: str, detail: str = "") -> None:
    passes.append(name)
    print(f"  PASS  {name}" + (f" — {detail}" if detail else ""))


def bad(name: str, detail: str) -> None:
    failures.append(name)
    print(f"  FAIL  {name} — {detail}")


def req(method: str, path: str, *, key: str | None = KEY_A, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/json"}
    if key:
        headers["X-API-Key"] = key
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return e.code, payload


def main() -> int:
    print(f"\n=== Gen 1 deep smoke @ {BASE} ===\n")

    # Health
    status, health = req("GET", "/healthz", key=None)
    if status == 200 and health.get("status") in {"ok", "degraded"}:
        ok("healthz", str(health.get("checks")))
        if health.get("checks", {}).get("postgres") == "ok":
            ok("healthz.postgres")
        else:
            bad("healthz.postgres", str(health))
        if health.get("checks", {}).get("redis") == "ok":
            ok("healthz.redis")
        else:
            bad("healthz.redis", str(health))
    else:
        bad("healthz", f"{status} {health}")

    # Auth
    status, body = req("GET", "/api/v1/weather/current?name=Harare", key=None)
    if status == 401:
        ok("auth.missing_key_401")
    else:
        bad("auth.missing_key_401", f"{status} {body}")

    # Weather suite + provenance + official/model
    for path, label in [
        ("/api/v1/weather/current?name=Harare", "weather.current"),
        ("/api/v1/weather/forecast?name=Harare&days=3", "weather.forecast"),
        ("/api/v1/weather/alerts?name=Harare", "weather.alerts"),
        ("/api/v1/weather/air-quality?name=Harare", "weather.aqi"),
        ("/api/v1/weather/agricultural?name=Harare", "weather.ag"),
        ("/api/v1/weather/compare?names=Harare,Bulawayo", "weather.compare"),
        ("/api/v1/weather/historical?name=Harare&start_date=2026-11-01&end_date=2026-11-03", "weather.historical"),
    ]:
        status, body = req("GET", path)
        if status == 200 and "provenance" in body and "data" in body:
            prov = body["provenance"]
            if all(k in prov for k in ("data_source", "confidence", "retrieved_at")):
                ok(label, prov.get("official_vs_model", ""))
            else:
                bad(label, f"missing provenance fields: {prov}")
        else:
            bad(label, f"{status} {body}")

    status, body = req(
        "POST",
        "/api/v1/weather/risk",
        body={
            "location": {"name": "Victoria Falls, Zimbabwe"},
            "activity": "outdoor_wedding",
            "on_date": "2026-11-20",
        },
    )
    if status == 200:
        wa = body["data"]["weather_assessment"]
        if wa.get("risk_level") and body["data"].get("recommendations") and body["data"].get("confidence"):
            ok("weather.risk_outdoor_wedding", wa["risk_level"])
        else:
            bad("weather.risk_outdoor_wedding", str(body["data"]))
        if body["provenance"].get("official_vs_model") in {"official", "model_derived", "mixed"}:
            ok("weather.official_vs_model_label")
        else:
            bad("weather.official_vs_model_label", str(body["provenance"]))
    else:
        bad("weather.risk_outdoor_wedding", f"{status} {body}")

    # Geo
    for path, label in [
        ("/api/v1/geo/geocode?address=Harare", "geo.geocode"),
        ("/api/v1/geo/nearby?name=Harare&radius_m=20000", "geo.nearby"),
        ("/api/v1/geo/emergency?name=Harare&type=hospital", "geo.emergency"),
    ]:
        status, body = req("GET", path)
        if status == 200 and "data" in body:
            ok(label)
        else:
            bad(label, f"{status} {body}")

    # Routing explainability + Harare->Bulawayo
    status, body = req(
        "POST",
        "/api/v1/routes/optimize",
        body={
            "origin": {"name": "Harare"},
            "destination": {"name": "Bulawayo"},
            "profile": "safest",
            "vehicle_class": "car",
        },
    )
    route_id = None
    if status == 200:
        routes = body["data"]["routes"]
        top = routes[0]
        route_id = body["data"]["route_id"]
        if top.get("cost_breakdown") and top.get("explanation"):
            ok("routing.explainability", top.get("label"))
        else:
            bad("routing.explainability", str(top))
        if top.get("label") != "Secondary via rain corridor" and "heavy_rain" not in top.get("hazards", []):
            ok("routing.avoids_flooded_corridor", str(top.get("hazards")))
        else:
            bad("routing.avoids_flooded_corridor", str(top))
        if all(r.get("closed") in (None, False) for r in routes):
            ok("routing.low_confidence_never_closes")
        else:
            bad("routing.low_confidence_never_closes", str(routes))
    else:
        bad("routing.optimize", f"{status} {body}")

    # Roads
    status, body = req("GET", "/api/v1/roads/incidents?area=Harare-Bulawayo")
    if status == 200 and isinstance(body.get("data", {}).get("incidents"), list):
        ok("roads.incidents", f"n={len(body['data']['incidents'])}")
    else:
        bad("roads.incidents", f"{status} {body}")

    status, body = req(
        "POST",
        "/api/v1/roads/reports",
        body={"location": {"name": "Harare"}, "type": "pothole", "severity": 2},
    )
    if status == 201 and body.get("data", {}).get("report_id"):
        ok("roads.report", body["data"]["report_id"])
    else:
        bad("roads.report", f"{status} {body}")

    # Journey + tenant isolation
    journey_id = None
    if route_id:
        status, body = req("POST", "/api/v1/journeys", body={"route_id": route_id})
        if status == 201:
            journey_id = body["data"]["id"]
            ok("journey.create", journey_id)
            status_a, _ = req("GET", f"/api/v1/journeys/{journey_id}")
            if status_a == 200:
                ok("journey.get_own")
            else:
                bad("journey.get_own", str(status_a))
            status_b, body_b = req("GET", f"/api/v1/journeys/{journey_id}", key=KEY_B)
            if status_b == 404 and body_b.get("code") == "NOT_FOUND" and "origin" not in body_b:
                ok("tenant_isolation.cross_tenant_404")
            else:
                bad("tenant_isolation.cross_tenant_404", f"{status_b} {body_b}")
        else:
            bad("journey.create", f"{status} {body}")

    # MCP initialize
    mcp_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "gen1-deep-smoke", "version": "0.1.0"},
        },
    }
    data = json.dumps(mcp_body).encode()
    request = urllib.request.Request(
        f"{BASE}/mcp/",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            payload = json.loads(resp.read().decode())
            if payload.get("result", {}).get("serverInfo", {}).get("name") == "mamiriro-megmis":
                ok("mcp.initialize", payload["result"]["serverInfo"].get("version"))
            else:
                bad("mcp.initialize", str(payload))
    except Exception as exc:  # noqa: BLE001
        bad("mcp.initialize", str(exc))

    # DB assertions
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        tenants = conn.execute(text("select count(*) from tenants")).scalar()
        keys = conn.execute(text("select count(*) from api_keys")).scalar()
        locs = conn.execute(text("select count(*) from locations")).scalar()
        incidents = conn.execute(text("select count(*) from incidents")).scalar()
        routes = conn.execute(text("select count(*) from routes")).scalar()
        journeys = conn.execute(text("select count(*) from journeys")).scalar()
        reports = conn.execute(text("select count(*) from road_reports")).scalar()
        if tenants and tenants >= 2:
            ok("db.tenants", str(tenants))
        else:
            bad("db.tenants", str(tenants))
        if keys and keys >= 2:
            ok("db.api_keys", str(keys))
        else:
            bad("db.api_keys", str(keys))
        if locs and locs >= 5:
            ok("db.locations", str(locs))
        else:
            bad("db.locations", str(locs))
        if incidents and incidents >= 1:
            ok("db.incidents", str(incidents))
        else:
            bad("db.incidents", str(incidents))
        if routes and routes >= 1:
            ok("db.routes", str(routes))
        else:
            bad("db.routes", str(routes))
        if journeys and journeys >= 1:
            ok("db.journeys", str(journeys))
        else:
            bad("db.journeys", str(journeys))
        if reports and reports >= 1:
            ok("db.road_reports", str(reports))
        else:
            bad("db.road_reports", str(reports))

        # geometry present
        geom = conn.execute(
            text("select count(*) from locations where geom is not null")
        ).scalar()
        if geom and geom >= 1:
            ok("db.postgis_geom_points", str(geom))
        else:
            bad("db.postgis_geom_points", str(geom))

    # Redis keys
    r = Redis.from_url(REDIS_URL, decode_responses=True)
    weather_keys = list(r.scan_iter("weather:*"))
    route_keys = list(r.scan_iter("route:*"))
    journey_keys = list(r.scan_iter("journey:*"))
    if weather_keys:
        ok("redis.weather_cache", f"n={len(weather_keys)}")
    else:
        bad("redis.weather_cache", "no weather:* keys")
    if route_keys:
        ok("redis.route_cache", f"n={len(route_keys)}")
    else:
        bad("redis.route_cache", "no route:* keys")
    if journey_keys:
        ok("redis.journey_state", f"n={len(journey_keys)}")
    else:
        bad("redis.journey_state", "no journey:* keys")

    # OSM extract
    osm = Path(__file__).resolve().parents[1] / "data/osm/zimbabwe-harare-bulawayo.osm"
    if osm.exists() and osm.stat().st_size > 100:
        ok("osm.extract", str(osm.name))
    else:
        bad("osm.extract", str(osm))

    print(f"\n=== Result: {len(passes)} passed, {len(failures)} failed ===")
    if failures:
        print("Failed:")
        for f in failures:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
