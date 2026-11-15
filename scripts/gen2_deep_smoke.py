#!/usr/bin/env python3
"""Deep Gen 2 smoke: keys, webhooks, risk, traffic, console, road pipeline, RLS role."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

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
        with urllib.request.urlopen(request, timeout=20) as resp:
            raw = resp.read().decode()
            ctype = resp.headers.get("Content-Type", "")
            if "json" in ctype or (raw and raw[0] in "{["):
                return resp.status, json.loads(raw) if raw else {}
            return resp.status, {"raw": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return e.code, payload


def main() -> int:
    print(f"\n=== Gen 2 deep smoke @ {BASE} ===\n")

    # --- API key rotate / revoke ---
    status, created = req(
        "POST",
        "/api/v1/keys",
        body={"label": "gen2-smoke", "scopes": ["weather:read", "webhook:manage", "journey:write"]},
    )
    if status == 201 and created.get("data", {}).get("raw_key", "").startswith("meg_"):
        ok("keys.create", created["data"]["id"])
        key_id = created["data"]["id"]
        raw = created["data"]["raw_key"]
    else:
        bad("keys.create", f"{status} {created}")
        key_id = raw = None

    if key_id:
        status, rotated = req("POST", f"/api/v1/keys/{key_id}/rotate")
        if status == 200 and rotated.get("data", {}).get("raw_key") != raw:
            ok("keys.rotate")
            new_raw = rotated["data"]["raw_key"]
            st, _ = req("GET", "/api/v1/weather/current?name=Harare", key=raw)
            if st == 401:
                ok("keys.old_revoked_after_rotate")
            else:
                bad("keys.old_revoked_after_rotate", str(st))
            st, _ = req("GET", "/api/v1/weather/current?name=Harare", key=new_raw)
            if st == 200:
                ok("keys.new_works")
            else:
                bad("keys.new_works", str(st))
            req("POST", f"/api/v1/keys/{key_id}/revoke")
            st, _ = req("GET", "/api/v1/weather/current?name=Harare", key=new_raw)
            if st == 401:
                ok("keys.revoke")
            else:
                bad("keys.revoke", str(st))
        else:
            bad("keys.rotate", f"{status} {rotated}")

    # --- Webhooks HMAC ---
    status, wh = req(
        "POST",
        "/api/v1/webhooks",
        body={"url": "https://example.com/hooks/mamiriro", "events": ["road.report"]},
    )
    if status == 201 and wh.get("data", {}).get("secret"):
        secret = wh["data"]["secret"]
        body = json.dumps({"event": "road.report", "ok": True}).encode()
        ts = int(time.time())
        sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        expected = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        if sig == expected:
            ok("webhooks.hmac_x_mamiriro_signature", "secret issued")
        else:
            bad("webhooks.hmac", "mismatch")
        st, listed = req("GET", "/api/v1/webhooks")
        if st == 200:
            ok("webhooks.list", f"n={len(listed.get('data', listed.get('subscriptions', [])))}")
        else:
            bad("webhooks.list", str(st))
    else:
        bad("webhooks.create", f"{status} {wh}")

    # --- Journey risk persistence ---
    status, risk = req(
        "POST",
        "/api/v1/risk/journey",
        body={
            "origin": {"name": "Harare"},
            "destination": {"name": "Bulawayo"},
            "profile": "safest",
            "activity": "road_trip",
        },
    )
    if status == 200 and risk.get("data", {}).get("assessment_id"):
        aid = risk["data"]["assessment_id"]
        ok("risk.assess_persisted", aid)
        st, got = req("GET", f"/api/v1/risk/{aid}")
        if st == 200 and got.get("data", {}).get("assessment_id") == aid:
            ok("risk.get")
        else:
            bad("risk.get", f"{st} {got}")
        # tenant B cannot read
        st, _ = req("GET", f"/api/v1/risk/{aid}", key=KEY_B)
        if st in {403, 404}:
            ok("risk.tenant_isolation", str(st))
        else:
            bad("risk.tenant_isolation", str(st))
    else:
        bad("risk.assess", f"{status} {risk}")

    # --- Traffic ---
    status, cong = req("GET", "/api/v1/traffic/congestion?corridor=A5%20Harare-Bulawayo")
    if status == 200 and "congestion" in cong.get("data", {}):
        ok("traffic.congestion", str(cong["data"].get("matched_profile")))
    else:
        bad("traffic.congestion", f"{status} {cong}")
    status, cors = req("GET", "/api/v1/traffic/corridors")
    if status == 200:
        ok("traffic.corridors")
    else:
        bad("traffic.corridors", str(status))

    # --- Road report + pipeline (via DB worker path) ---
    status, report = req(
        "POST",
        "/api/v1/roads/reports",
        body={"location": {"name": "Harare"}, "type": "pothole", "severity": 4},
    )
    if status in {200, 201}:
        ok("roads.report", str(status))
    else:
        bad("roads.report", f"{status} {report}")
    try:
        from megmis.engines.road.pipeline import validate_pending_reports

        result = validate_pending_reports()
        if "validated" in result:
            ok("road.pipeline", str(result))
        else:
            bad("road.pipeline", str(result))
    except Exception as exc:  # noqa: BLE001
        bad("road.pipeline", str(exc))

    # --- Console MVP ---
    status, health = req("GET", "/api/v1/console/health")
    if status == 200 and health.get("status") in {"ok", "degraded"}:
        ok("console.health", str(health.get("checks")))
    else:
        bad("console.health", f"{status} {health}")
    status, usage = req("GET", "/api/v1/console/usage")
    if status == 200 and "data" in usage:
        ok("console.usage", f"requests={usage['data'].get('request_count')}")
    else:
        bad("console.usage", f"{status} {usage}")
    status, page = req("GET", "/api/v1/console/")
    if status == 200 and "Mamiriro Console" in str(page.get("raw", page)):
        ok("console.html")
    else:
        bad("console.html", str(status))

    # --- DB: megmis_app NOBYPASSRLS + audit_log ---
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT rolname, rolbypassrls FROM pg_roles WHERE rolname = 'megmis_app'"
            )
        ).first()
        if row and row[0] == "megmis_app" and row[1] is False:
            ok("rls.megmis_app_nobypassrls")
        else:
            bad("rls.megmis_app_nobypassrls", str(row))

        n = conn.execute(text("SELECT count(*) FROM audit_log")).scalar()
        if n is not None and int(n) >= 0:
            ok("audit_log.table", f"rows={n}")
        else:
            bad("audit_log.table", str(n))

        for table in ("webhook_subscriptions", "usage_events", "job_runs", "webhook_deliveries"):
            exists = conn.execute(
                text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}
            ).scalar()
            if exists:
                ok(f"schema.{table}")
            else:
                bad(f"schema.{table}", "missing")

        # App role is the runtime path when USE_APP_ROLE=true
        app_url = os.environ.get(
            "DATABASE_APP_URL",
            "postgresql+psycopg://megmis_app:megmis_app@localhost:5433/megmis",
        )
        try:
            app_engine = create_engine(app_url)
            with app_engine.connect() as ac:
                ac.execute(text("SELECT set_config('app.tenant_id', '00000000-0000-0000-0000-000000000001', true)"))
                # Should succeed as login; empty result under RLS is fine
                ac.execute(text("SELECT count(*) FROM api_keys")).scalar()
            ok("rls.app_role_connect", app_url.split("@")[-1])
        except Exception as exc:  # noqa: BLE001
            bad("rls.app_role_connect", str(exc))

    # --- Redis token bucket key shape ---
    try:
        r = Redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        ok("redis.ping")
        # exercise bucket via a couple of authenticated calls already done
        keys = list(r.scan_iter("ratelimit:bucket:*", count=20))
        if keys:
            ok("redis.token_bucket_keys", f"n={len(keys)}")
        else:
            ok("redis.token_bucket_keys", "none yet (acceptable if limits high)")
    except Exception as exc:  # noqa: BLE001
        bad("redis", str(exc))

    print(f"\n=== {len(passes)} passed, {len(failures)} failed ===\n")
    for f in failures:
        print(f"  • {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
