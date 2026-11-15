from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.engines.routing import traffic

router = APIRouter(prefix="/traffic", tags=["traffic"])


@router.get("/congestion")
async def congestion(
    corridor: str,
    at_time: datetime | None = None,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "routing:read")
    return {"data": traffic.get_congestion(corridor, at_time)}


@router.get("/estimate")
async def estimate(
    corridor: str,
    duration_s: float,
    at_time: datetime | None = None,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "routing:read")
    return {"data": traffic.estimate_time_at(duration_s, corridor, at_time)}


@router.get("/corridors")
async def corridors(tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    return {"data": {"corridors": traffic.list_corridors()}}
