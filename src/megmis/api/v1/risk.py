from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.common.schemas import LocationInput
from megmis.engines.risk import RiskService

router = APIRouter(prefix="/risk", tags=["risk"])
_service = RiskService()


class JourneyRiskRequest(BaseModel):
    origin: LocationInput
    destination: LocationInput
    profile: str = "safest"
    activity: str | None = "road_trip"


@router.post("/journey")
async def assess_journey_risk(body: JourneyRiskRequest, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "journey:write")
    return _service.assess_journey(
        body.origin,
        body.destination,
        profile=body.profile,
        tenant_id=str(tenant.tenant_id),
        activity=body.activity,
    ).model_dump(mode="json")


@router.get("/{assessment_id}")
async def get_assessment(assessment_id: str, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "journey:write")
    return _service.get_assessment(assessment_id, str(tenant.tenant_id)).model_dump(mode="json")
