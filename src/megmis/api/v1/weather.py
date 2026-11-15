from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.common.schemas import LocationInput
from megmis.engines.weather import WeatherService

router = APIRouter(prefix="/weather", tags=["weather"])
_service = WeatherService()


class RiskRequest(BaseModel):
    location: LocationInput
    activity: str
    on_date: date | None = None


class ActivitiesRequest(BaseModel):
    location: LocationInput
    on_date: date | None = None


class CompareRequest(BaseModel):
    locations: list[LocationInput] = Field(min_length=1)


def _loc(lat: float | None, lon: float | None, name: str | None) -> LocationInput:
    return LocationInput(lat=lat, lon=lon, name=name)


@router.get("/current")
async def current(
    lat: float | None = None,
    lon: float | None = None,
    name: str | None = None,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "weather:read")
    return _service.current(_loc(lat, lon, name)).model_dump(mode="json")


@router.get("/forecast")
async def forecast(
    lat: float | None = None,
    lon: float | None = None,
    name: str | None = None,
    days: int = Query(7, ge=1, le=14),
    hourly: bool = False,
    on_date: date | None = None,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "weather:read")
    loc = _loc(lat, lon, name)
    if hourly:
        return _service.hourly(loc, on_date or date.today()).model_dump(mode="json")
    return _service.forecast(loc, days).model_dump(mode="json")


@router.get("/alerts")
async def alerts(
    lat: float | None = None,
    lon: float | None = None,
    name: str | None = None,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "weather:read")
    return _service.alerts(_loc(lat, lon, name)).model_dump(mode="json")


@router.get("/compare")
async def compare(
    names: str = Query(..., description="Comma-separated place names"),
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "weather:read")
    locations = [LocationInput(name=n.strip()) for n in names.split(",") if n.strip()]
    return _service.compare(locations).model_dump(mode="json")


@router.get("/historical")
async def historical(
    start_date: date,
    end_date: date,
    lat: float | None = None,
    lon: float | None = None,
    name: str | None = None,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "weather:read")
    return _service.historical(_loc(lat, lon, name), start_date, end_date).model_dump(mode="json")


@router.get("/air-quality")
async def air_quality(
    lat: float | None = None,
    lon: float | None = None,
    name: str | None = None,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "weather:read")
    return _service.air_quality(_loc(lat, lon, name)).model_dump(mode="json")


@router.get("/agricultural")
async def agricultural(
    lat: float | None = None,
    lon: float | None = None,
    name: str | None = None,
    tenant: TenantContext = Depends(get_tenant),
):
    require_scope(tenant, "weather:read")
    return _service.agricultural(_loc(lat, lon, name)).model_dump(mode="json")


@router.post("/risk")
async def risk(body: RiskRequest, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "weather:read")
    return _service.analyze_risk(body.location, body.activity, body.on_date).model_dump(mode="json")


@router.post("/activities")
async def activities(body: ActivitiesRequest, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "weather:read")
    return _service.recommend_activities(body.location, body.on_date).model_dump(mode="json")
