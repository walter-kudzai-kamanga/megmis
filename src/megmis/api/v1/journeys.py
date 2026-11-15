from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.engines.routing import RoutingService

router = APIRouter(prefix="/journeys", tags=["journeys"])
_service = RoutingService()


class CreateJourney(BaseModel):
    route_id: str


@router.post("", status_code=201)
async def create_journey(body: CreateJourney, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "journey:write")
    return _service.create_journey(body.route_id, str(tenant.tenant_id)).model_dump(mode="json")


@router.get("/{journey_id}")
async def get_journey(journey_id: str, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "journey:write")
    return _service.get_journey(journey_id, str(tenant.tenant_id)).model_dump(mode="json")
