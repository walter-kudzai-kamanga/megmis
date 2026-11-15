from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.common.schemas import LocationInput
from megmis.engines.road import RoadService

router = APIRouter(prefix="/roads", tags=["roads"])
_service = RoadService()


class ReportRequest(BaseModel):
    location: LocationInput
    type: str
    severity: int = Field(ge=1, le=5)
    evidence_refs: list[str] = Field(default_factory=list)


@router.post("/reports", status_code=201)
async def reports(body: ReportRequest, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "road:write")
    return _service.report(
        body.location,
        body.type,
        body.severity,
        body.evidence_refs,
        tenant_id=str(tenant.tenant_id),
    ).model_dump(mode="json")


@router.get("/incidents")
async def incidents(
    area: str | None = None,
    corridor: str | None = None,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "road:read")
    return _service.incidents(area=area, corridor=corridor).model_dump(mode="json")
