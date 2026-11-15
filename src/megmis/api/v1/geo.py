from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.common.schemas import LocationInput
from megmis.engines.geo import GeoService

router = APIRouter(prefix="/geo", tags=["geo"])
_service = GeoService()


@router.get("/geocode")
async def geocode(
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "geo:read")
    if address:
        return _service.geocode(address).model_dump(mode="json")
    if lat is not None and lon is not None:
        return _service.reverse(lat, lon).model_dump(mode="json")
    from megmis.common.errors import AppError

    raise AppError("INVALID_LOCATION", "Provide address or lat/lon")


@router.get("/nearby")
async def nearby(
    lat: float | None = None,
    lon: float | None = None,
    name: str | None = None,
    category: str | None = None,
    radius_m: int = Query(5000, ge=100, le=100_000),
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "geo:read")
    return _service.nearby(LocationInput(lat=lat, lon=lon, name=name), category, radius_m).model_dump(
        mode="json"
    )


@router.get("/emergency")
async def emergency(
    lat: float | None = None,
    lon: float | None = None,
    name: str | None = None,
    type: str | None = None,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "geo:read")
    return _service.emergency(LocationInput(lat=lat, lon=lon, name=name), type).model_dump(mode="json")
