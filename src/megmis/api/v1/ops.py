"""Gen 4 ops surface — metrics, provider health, calibration, retention."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.common.observability import metrics
from megmis.engines.routing import calibration
from megmis.providers.factory import clear_provider_caches
from megmis.providers.orchestrator import get_orchestrator
from megmis.storage.object_store import get_object_store

router = APIRouter(tags=["ops"])


class GpsPoint(BaseModel):
    lat: float
    lon: float
    ts: datetime | None = None
    speed_mps: float | None = None


class TraceIngest(BaseModel):
    points: list[GpsPoint] = Field(min_length=2)
    profile: str = "safest"
    route_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class CalibrateRequest(BaseModel):
    profile: str = "safest"
    min_traces: int = 3


@router.get("/metrics")
async def prometheus_metrics():
    return Response(content=metrics.prometheus(), media_type="text/plain; version=0.0.4")


@router.get("/ops/metrics")
async def json_metrics(tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    return {"data": metrics.snapshot()}


@router.get("/ops/providers")
async def provider_health(tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    orch = get_orchestrator()
    return {"data": orch.health_snapshot()}


@router.post("/ops/providers/probe")
async def provider_probe(tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    orch = get_orchestrator()
    results = orch.run_health_probes()
    clear_provider_caches()
    return {"data": {"probes": results, "snapshot": orch.health_snapshot()}}


@router.post("/ops/traces", status_code=201)
async def ingest_trace(body: TraceIngest, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    row = calibration.ingest_trace(
        str(tenant.tenant_id),
        points=[p.model_dump(mode="json") for p in body.points],
        profile=body.profile,
        route_id=body.route_id,
        meta=body.meta,
    )
    return {"data": row}


@router.get("/ops/traces")
async def list_traces(tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    return {"data": {"traces": calibration.list_traces(str(tenant.tenant_id))}}


@router.post("/ops/calibrate")
async def calibrate(body: CalibrateRequest, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    result = calibration.calibrate_weights(
        str(tenant.tenant_id), profile=body.profile, min_traces=body.min_traces
    )
    return {"data": result}


@router.get("/ops/weights")
async def weights(tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    return {"data": {"weights": calibration.current_weights()}}


@router.post("/ops/storage/purge")
async def purge_storage(tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "webhook:manage")
    result = get_object_store().purge_expired()
    return {"data": result}


@router.post("/ops/storage/put-demo")
async def put_demo_object(tenant: TenantContext = Depends(get_tenant)):
    """Store a tiny evidence blob (tests object-store + retention metadata)."""
    require_scope(tenant, "road:write")
    from datetime import datetime

    from megmis.config import get_settings
    from megmis.db import models
    from megmis.db.session import session_scope

    store = get_object_store()
    settings = get_settings()
    obj = store.put(
        b"megmis-evidence-demo",
        prefix="evidence",
        content_type="text/plain",
        retention_days=settings.evidence_retention_days,
    )
    if settings.use_persistence:
        try:
            with session_scope(tenant_id=str(tenant.tenant_id)) as session:
                session.add(
                    models.ObjectArtefact(
                        tenant_id=tenant.tenant_id,
                        key=obj.key,
                        uri=obj.uri,
                        kind="evidence",
                        content_type=obj.content_type,
                        bytes=obj.bytes,
                        retention_days=obj.retention_days,
                        expires_at=datetime.fromisoformat(obj.expires_at),
                        meta={},
                    )
                )
        except Exception:
            pass
    return {"data": obj.__dict__}
