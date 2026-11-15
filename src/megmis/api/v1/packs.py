from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.common.schemas import LocationInput
from megmis.engines.packs import PackService

router = APIRouter(prefix="/packs", tags=["packs"])
_service = PackService()


class PackRunRequest(BaseModel):
    origin: LocationInput | None = None
    destination: LocationInput | None = None
    location: LocationInput | None = None
    profile: str = "safest"


@router.get("")
async def list_packs(tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "routing:read")
    return {"data": {"packs": _service.list_packs()}}


@router.post("/{pack_id}/run")
async def run_pack(
    pack_id: str,
    body: PackRunRequest,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "routing:read")
    return _service.run_pack(
        pack_id,
        origin=body.origin,
        destination=body.destination,
        location=body.location,
        tenant_id=str(tenant.tenant_id),
        profile=body.profile,
    ).model_dump(mode="json")
