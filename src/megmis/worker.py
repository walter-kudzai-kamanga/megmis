"""Async worker: road validation, weather alert fan-out, webhook drain, graph refresh."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import select

from megmis.api.v1.webhooks import enqueue_event, process_pending_deliveries
from megmis.common.schemas import LocationInput
from megmis.common.zimbabwe import KNOWN_PLACES
from megmis.config import get_settings
from megmis.db.models import JobRun, Tenant
from megmis.db.session import session_scope
from megmis.engines.road.pipeline import validate_pending_reports
from megmis.engines.weather.service import WeatherService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("megmis.worker")


def _record_job(job_type: str, payload: dict, result: dict, status: str = "completed") -> None:
    try:
        with session_scope(admin=True) as session:
            session.add(
                JobRun(
                    id=uuid4(),
                    job_type=job_type,
                    payload=payload,
                    status=status,
                    result=result,
                    finished_at=datetime.now(UTC),
                )
            )
    except Exception:
        log.exception("failed to record job_run")


def job_validate_reports() -> dict:
    result = validate_pending_reports()
    _record_job("road_validation", {}, result)
    log.info("road_validation %s", result)
    return result


def job_webhook_drain() -> dict:
    results = process_pending_deliveries(limit=100)
    delivered = sum(1 for r in results if r.get("ok"))
    failed = len(results) - delivered
    out = {"processed": len(results), "delivered": delivered, "failed": failed}
    _record_job("webhook_drain", {}, out)
    log.info("webhook_drain %s", out)
    return out


def job_weather_alerts_fanout() -> dict:
    """Scan key Zimbabwe cities for alerts and enqueue webhook deliveries per tenant."""
    weather = WeatherService()
    alerts_scanned = 0
    enqueued = 0
    cities = [n.title() for n in list(KNOWN_PLACES.keys())[:5]] or ["Harare", "Bulawayo", "Mutare"]

    alert_payloads: list[dict] = []
    for name in cities:
        try:
            env = weather.alerts(LocationInput(name=name))
            items = (env.data or {}).get("alerts") or []
            alerts_scanned += len(items)
            for a in items:
                alert_payloads.append({"location": name, "alert": a})
        except Exception:
            log.exception("alert_scan_failed location=%s", name)

    if not alert_payloads:
        alert_payloads.append(
            {
                "location": "Harare",
                "alert": {
                    "severity": "info",
                    "event": "worker_heartbeat",
                    "description": "No active alerts; Gen 2 fanout heartbeat",
                },
            }
        )

    with session_scope(admin=True) as session:
        tenant_ids = [
            str(t.id)
            for t in session.scalars(select(Tenant).where(Tenant.status == "active")).all()
        ]

    for tid in tenant_ids:
        for payload in alert_payloads:
            ids = enqueue_event(tid, "alert.weather", payload)
            enqueued += len(ids)

    drain = process_pending_deliveries(limit=50)
    result = {
        "alerts_scanned": alerts_scanned,
        "enqueued": enqueued,
        "drain": {"processed": len(drain), "ok": sum(1 for r in drain if r.get("ok"))},
    }
    _record_job("weather_alerts", {"cities": cities}, result)
    log.info("weather_alerts %s", result)
    return result


def job_graph_refresh() -> dict:
    """
    Prepare routing graph refresh from OSM extract.
    Validates extract + checksum, writes blue/green intent marker, probes providers.
    """
    settings = get_settings()
    osm = Path(settings.osm_extract_path)
    out_dir = Path(settings.graph_refresh_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not osm.exists():
        result = {"status": "missing_extract", "path": str(osm)}
        _record_job("graph_refresh", {"path": str(osm)}, result, status="failed")
        log.warning("graph_refresh %s", result)
        return result

    digest = hashlib.sha256(osm.read_bytes()).hexdigest()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    marker = out_dir / f"refresh_{stamp}.json"
    intent: dict = {
        "status": "ready_for_swap",
        "osm_extract": str(osm),
        "sha256": digest,
        "bytes": osm.stat().st_size,
        "requested_at": datetime.now(UTC).isoformat(),
        "note": "Ops: build new graph tile set, health-check, then atomic symlink swap",
    }

    probes: dict[str, str] = {}
    if settings.valhalla_url:
        try:
            r = httpx.get(f"{settings.valhalla_url.rstrip('/')}/status", timeout=5.0)
            probes["valhalla"] = f"http_{r.status_code}"
        except Exception as exc:  # noqa: BLE001
            probes["valhalla"] = f"error:{exc.__class__.__name__}"
    if settings.graphhopper_url:
        try:
            r = httpx.get(f"{settings.graphhopper_url.rstrip('/')}/health", timeout=5.0)
            probes["graphhopper"] = f"http_{r.status_code}"
        except Exception as exc:  # noqa: BLE001
            probes["graphhopper"] = f"error:{exc.__class__.__name__}"

    intent["provider_probes"] = probes
    marker.write_text(json.dumps(intent, indent=2))
    (out_dir / "latest.json").write_text(marker.read_text())

    result = {**intent, "marker": str(marker)}
    _record_job("graph_refresh", {"path": str(osm)}, result)
    log.info(
        "graph_refresh %s",
        {"status": result["status"], "sha256": digest[:12], "probes": probes},
    )
    return result


def job_provider_health() -> dict:
    from megmis.providers.orchestrator import get_orchestrator

    results = get_orchestrator().run_health_probes()
    _record_job("provider_health", {}, results)
    log.info("provider_health %s", results)
    return results


def job_object_retention() -> dict:
    from megmis.storage.object_store import get_object_store

    result = get_object_store().purge_expired()
    _record_job("object_retention", {}, result)
    log.info("object_retention %s", result)
    return result


def run_once() -> None:
    job_validate_reports()
    job_weather_alerts_fanout()
    job_webhook_drain()
    job_graph_refresh()
    job_provider_health()
    job_object_retention()


def main() -> None:
    settings = get_settings()
    interval = int(getattr(settings, "worker_interval_seconds", 60) or 60)
    log.info(
        "megmis worker starting interval=%ss use_app_role=%s",
        interval,
        settings.effective_use_app_role,
    )
    while True:
        try:
            run_once()
        except Exception:
            log.exception("worker loop error")
        time.sleep(interval)


if __name__ == "__main__":
    main()
