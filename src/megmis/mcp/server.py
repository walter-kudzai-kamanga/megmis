from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer

from megmis.common.errors import AppError
from megmis.common.schemas import Confidence, Envelope, LocationInput, Provenance, new_request_id
from megmis.mcp.runtime import (
    _READ,
    _WRITE,
    MCP_SERVER_NAME,
    MCP_TITLE,
    MCP_VERSION,
    clamp_days,
    clamp_radius_m,
    clamp_severity,
    dump,
    geo,
    loc,
    require_latlon_position,
    require_nonempty,
    require_tenant,
    reset_mcp_services,
    resolve_tenant,
    road,
    routing,
    safe_tool,
    weather,
)

mcp = MCPServer(
    "mamiriro-megmis",
    version=MCP_VERSION,
    instructions=(
        f"{MCP_TITLE} ({MCP_SERVER_NAME}) intelligence tools for weather, geospatial, "
        "routing, and road conditions in Zimbabwe and beyond. Prefer named places or lat/lon. "
        "Every tool returns data plus provenance and meta.x-mcp-version. "
        "Mutating tools (report_road_condition, create_journey, reroute) require a tenant "
        "via X-API-Key on /mcp or an api_key argument (stdio seeds the demo tenant)."
    ),
)


@mcp.tool(annotations=_READ)
@safe_tool
def get_current_weather(location: dict[str, Any]) -> dict[str, Any]:
    """Current weather for a location ({lat,lon} or {name})."""
    return dump(weather.current(loc(location)))


@mcp.tool(annotations=_READ)
@safe_tool
def get_forecast(location: dict[str, Any], days: int = 7) -> dict[str, Any]:
    """Daily forecast (1-14 days)."""
    return dump(weather.forecast(loc(location), clamp_days(days)))


@mcp.tool(annotations=_READ)
@safe_tool
def get_hourly_forecast(location: dict[str, Any], date: str) -> dict[str, Any]:
    """Hourly forecast for a specific ISO date (YYYY-MM-DD)."""
    from datetime import date as date_cls

    return dump(weather.hourly(loc(location), date_cls.fromisoformat(date)))


@mcp.tool(annotations=_READ)
@safe_tool
def get_weather_alerts(location: dict[str, Any]) -> dict[str, Any]:
    """Active weather alerts; official warnings labelled separately from model-derived."""
    return dump(weather.alerts(loc(location)))


@mcp.tool(annotations=_READ)
@safe_tool
def compare_weather(locations: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare current weather across multiple locations."""
    if not locations:
        raise AppError("INVALID_PARAMS", "locations must be a non-empty list", status_code=400)
    return dump(weather.compare([loc(item) for item in locations]))


@mcp.tool(annotations=_READ)
@safe_tool
def get_historical_weather(
    location: dict[str, Any], start_date: str, end_date: str
) -> dict[str, Any]:
    """Historical weather observations between ISO dates."""
    from datetime import date as date_cls

    start = date_cls.fromisoformat(start_date)
    end = date_cls.fromisoformat(end_date)
    if end < start:
        raise AppError("INVALID_PARAMS", "end_date must be on or after start_date", status_code=400)
    return dump(weather.historical(loc(location), start, end))


@mcp.tool(annotations=_READ)
@safe_tool
def get_air_quality(location: dict[str, Any]) -> dict[str, Any]:
    """Air quality index and pollutants for a location."""
    return dump(weather.air_quality(loc(location)))


@mcp.tool(annotations=_READ)
@safe_tool
def get_agricultural_conditions(location: dict[str, Any]) -> dict[str, Any]:
    """Agricultural / growing-condition indicators."""
    return dump(weather.agricultural(loc(location)))


@mcp.tool(annotations=_READ)
@safe_tool
def analyze_weather_risk(
    location: dict[str, Any], activity: str, date: str | None = None
) -> dict[str, Any]:
    """Activity-based weather risk (e.g. outdoor_wedding) with recommendations."""
    from datetime import date as date_cls

    require_nonempty(activity, "activity")
    on = date_cls.fromisoformat(date) if date else None
    return dump(weather.analyze_risk(loc(location), activity, on))


@mcp.tool(annotations=_READ)
@safe_tool
def recommend_outdoor_activities(
    location: dict[str, Any], date: str | None = None
) -> dict[str, Any]:
    """Suitability scores for common outdoor activities."""
    from datetime import date as date_cls

    on = date_cls.fromisoformat(date) if date else None
    return dump(weather.recommend_activities(loc(location), on))


@mcp.tool(annotations=_READ)
@safe_tool
def geocode(address: str) -> dict[str, Any]:
    """Geocode an address or place name to coordinates."""
    return dump(geo.geocode(require_nonempty(address, "address")))


@mcp.tool(annotations=_READ)
@safe_tool
def reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    """Reverse-geocode coordinates to an address."""
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise AppError("INVALID_PARAMS", "lat/lon out of range", status_code=400)
    return dump(geo.reverse(lat, lon))


@mcp.tool(annotations=_READ)
@safe_tool
def find_nearby_places(
    location: dict[str, Any], category: str | None = None, radius_m: int = 5000
) -> dict[str, Any]:
    """Find nearby places by optional category within radius_m."""
    return dump(geo.nearby(loc(location), category, clamp_radius_m(radius_m)))


@mcp.tool(annotations=_READ)
@safe_tool
def get_emergency_facilities(
    location: dict[str, Any], type: str | None = None
) -> dict[str, Any]:
    """Nearby emergency facilities (hospital, police, fire)."""
    return dump(geo.emergency(loc(location), type))


@mcp.tool(annotations=_READ)
@safe_tool
def optimize_route(
    origin: dict[str, Any],
    destination: dict[str, Any],
    waypoints: list[dict[str, Any]] | None = None,
    vehicle_class: str = "car",
    priorities: list[str] | None = None,
    departure_time: str | None = None,
    profile: str = "safest",
) -> dict[str, Any]:
    """Ranked routes with cost_breakdown and explanation (shortest is not always best)."""
    dep = None
    if departure_time:
        from datetime import datetime

        dep = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
    return dump(
        routing.optimize(
            loc(origin),
            loc(destination),
            waypoints=[loc(w) for w in (waypoints or [])],
            profile=profile,
            vehicle_class=vehicle_class,
            departure_time=dep,
            priorities=priorities,
        )
    )


@mcp.tool(annotations=_WRITE)
@safe_tool
def create_journey(route_id: str, api_key: str | None = None) -> dict[str, Any]:
    """Create an active journey from a route_id returned by optimize_route (requires auth)."""
    tenant = require_tenant(api_key, scope="journey:write", mutating=True)
    return dump(routing.create_journey(require_nonempty(route_id, "route_id"), str(tenant.tenant_id)))


@mcp.tool(annotations=_WRITE)
@safe_tool
def reroute(
    journey_id: str,
    current_position: dict[str, Any],
    reason: str = "conditions_changed",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Recompute alternatives for an active journey (requires auth)."""
    tenant = require_tenant(api_key, scope="journey:write", mutating=True)
    return dump(
        routing.reroute(
            require_nonempty(journey_id, "journey_id"),
            require_latlon_position(current_position),
            reason,
            tenant_id=str(tenant.tenant_id),
        )
    )


@mcp.tool(annotations=_READ)
@safe_tool
def get_route_conditions(
    route_id: str | None = None, corridor: str | None = None
) -> dict[str, Any]:
    """Weather, traffic and road-condition summary for a route or corridor."""
    if not route_id and not corridor:
        raise AppError("INVALID_PARAMS", "Provide route_id or corridor", status_code=400)
    return dump(routing.route_conditions(route_id=route_id, corridor=corridor))


@mcp.tool(annotations=_WRITE)
@safe_tool
def report_road_condition(
    location: dict[str, Any],
    type: str,
    severity: int,
    evidence_refs: list[str] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Submit a crowdsourced road-condition report (requires auth + road:write)."""
    require_tenant(api_key, scope="road:write", mutating=True)
    return dump(
        road.report(
            loc(location),
            require_nonempty(type, "type"),
            clamp_severity(severity),
            evidence_refs,
        )
    )


@mcp.tool(annotations=_READ)
@safe_tool
def get_road_incidents(
    area: str | None = None, corridor: str | None = None
) -> dict[str, Any]:
    """List road incidents for an area or corridor."""
    return dump(road.incidents(area=area, corridor=corridor))


@mcp.tool(annotations=_READ)
@safe_tool
def assess_journey_risk(
    origin: dict[str, Any],
    destination: dict[str, Any],
    profile: str = "safest",
    activity: str = "road_trip",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Composite journey risk from weather + routing + road; persists when tenant is known.

    Tenant resolution order: explicit api_key arg → request ContextVar (X-API-Key on /mcp)
    → default demo tenant when persistence is on.
    """
    from megmis.common.auth import seed_dev_key
    from megmis.config import get_settings
    from megmis.engines.risk import RiskService

    settings = get_settings()
    tenant_id: str | None = None
    ctx = resolve_tenant(api_key)
    if ctx is not None:
        tenant_id = str(ctx.tenant_id)
    elif settings.use_persistence:
        demo = seed_dev_key(settings)
        tenant_id = str(demo.tenant_id)

    return dump(
        RiskService().assess_journey(
            loc(origin),
            loc(destination),
            profile=profile,
            activity=activity,
            tenant_id=tenant_id,
        )
    )


@mcp.tool(annotations=_READ)
@safe_tool
def get_traffic_congestion(corridor: str) -> dict[str, Any]:
    """Traffic sub-module congestion estimate for a corridor."""
    from megmis.engines.routing import traffic

    data = traffic.get_congestion(require_nonempty(corridor, "corridor"))
    return dump(
        Envelope(
            data=data,
            provenance=Provenance(
                data_source="traffic-submodule",
                confidence=Confidence.medium,
            ),
            request_id=new_request_id(),
        )
    )


@mcp.tool(annotations=_READ)
@safe_tool
def list_service_packs() -> dict[str, Any]:
    """List Insurance / GovTech commercial service packs (Gen 4)."""
    from megmis.engines.packs import PackService

    packs = PackService().list_packs()
    return dump(
        Envelope(
            data={"packs": packs},
            provenance=Provenance(data_source="packs", confidence=Confidence.high),
            request_id=new_request_id(),
        )
    )


@mcp.tool(annotations=_READ)
@safe_tool
def run_service_pack(
    pack_id: str,
    origin: dict[str, Any] | None = None,
    destination: dict[str, Any] | None = None,
    location: dict[str, Any] | None = None,
    profile: str = "safest",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Run a commercial pack: insurance.corridor | govtech.emergency | govtech.mobility."""
    from megmis.engines.packs import PackService

    ctx = resolve_tenant(api_key)
    tenant_id = str(ctx.tenant_id) if ctx else None
    return dump(
        PackService().run_pack(
            require_nonempty(pack_id, "pack_id"),
            origin=loc(origin) if origin else None,
            destination=loc(destination) if destination else None,
            location=loc(location) if location else None,
            tenant_id=tenant_id,
            profile=profile,
        )
    )


@mcp.resource("weather://current/{location}")
def resource_current_weather(location: str) -> str:
    """Current weather resource for a named location."""
    return json.dumps(dump(weather.current(LocationInput(name=location))), indent=2)


@mcp.resource("weather://forecast/{location}")
def resource_forecast(location: str) -> str:
    return json.dumps(dump(weather.forecast(LocationInput(name=location))), indent=2)


@mcp.resource("weather://alerts/{location}")
def resource_alerts(location: str) -> str:
    return json.dumps(dump(weather.alerts(LocationInput(name=location))), indent=2)


@mcp.resource("weather://historical/{location}")
def resource_historical(location: str) -> str:
    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=7)
    return json.dumps(
        dump(weather.historical(LocationInput(name=location), start, end)),
        indent=2,
    )


@mcp.resource("road://incidents/{area}")
def resource_incidents(area: str) -> str:
    return json.dumps(dump(road.incidents(area=area)), indent=2)


@mcp.resource("route://journey/{journey_id}")
def resource_journey(journey_id: str) -> str:
    # Public resource view; tenant check applies on REST. Gen 1 returns not-found safely.
    from megmis.engines.routing.service import _JOURNEYS

    journey = _JOURNEYS.get(journey_id)
    return json.dumps(journey or {"error": "not_found"}, indent=2)


@mcp.prompt()
def plan_trip(origin: str, destination: str) -> str:
    return (
        f"Plan a trip from {origin} to {destination}. "
        "Use geocode, get_weather_alerts, get_road_incidents, and optimize_route "
        "(profile=safest). Explain trade-offs using cost_breakdown. "
        "Call create_journey with the route_id when ready to monitor."
    )


@mcp.prompt()
def assess_weather_risk(location: str, activity: str, date: str) -> str:
    return (
        f"Assess weather risk for {activity} at {location} on {date}. "
        "Call analyze_weather_risk and get_weather_alerts. Distinguish official vs model data."
    )


@mcp.prompt()
def prepare_outdoor_event(location: str, date: str) -> str:
    return (
        f"Prepare recommendations for an outdoor event at {location} on {date}. "
        "Use recommend_outdoor_activities and analyze_weather_risk."
    )


@mcp.prompt()
def analyze_agricultural_conditions(location: str) -> str:
    return (
        f"Analyse agricultural conditions near {location} using "
        "get_agricultural_conditions and get_forecast."
    )


@mcp.prompt()
def plan_delivery_route(origin: str, destination: str, vehicle_class: str = "light_truck") -> str:
    return (
        f"Plan a delivery from {origin} to {destination} for vehicle_class={vehicle_class}. "
        "Use optimize_route with profile=fuel or safest and cite hazards."
    )


@mcp.prompt(name="assess_journey_risk")
def prompt_assess_journey_risk(origin: str, destination: str) -> str:
    return (
        f"Assess end-to-end journey risk from {origin} to {destination}. "
        "Call assess_journey_risk tool; combine weather, road incidents and route explanations."
    )


def create_mcp_server() -> MCPServer:
    return mcp


__all__ = ["create_mcp_server", "mcp", "reset_mcp_services"]
