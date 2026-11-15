from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.common.schemas import LatLon, LocationInput
from megmis.engines.routing import RoutingService

router = APIRouter(prefix="/routes", tags=["routes"])
_service = RoutingService()


class OptimizeRequest(BaseModel):
    origin: LocationInput
    destination: LocationInput
    waypoints: list[LocationInput] = Field(default_factory=list)
    profile: str = "safest"
    vehicle_class: str = "car"
    departure_time: datetime | None = None
    priorities: list[str] = Field(default_factory=list)


class RerouteRequest(BaseModel):
    journey_id: str
    current_position: LatLon
    reason: str = "conditions_changed"


@router.post("/optimize")
async def optimize(body: OptimizeRequest, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    return _service.optimize(
        body.origin,
        body.destination,
        waypoints=body.waypoints,
        profile=body.profile,
        vehicle_class=body.vehicle_class,
        departure_time=body.departure_time,
        priorities=body.priorities,
        tenant_id=str(tenant.tenant_id),
    ).model_dump(mode="json")


@router.post("/reroute")
async def reroute(body: RerouteRequest, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    return _service.reroute(
        body.journey_id,
        body.current_position,
        body.reason,
        tenant_id=str(tenant.tenant_id),
    ).model_dump(mode="json")


@router.get("/{route_id}/conditions")
async def conditions(route_id: str, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    return _service.route_conditions(
        route_id=route_id, tenant_id=str(tenant.tenant_id)
    ).model_dump(mode="json")
