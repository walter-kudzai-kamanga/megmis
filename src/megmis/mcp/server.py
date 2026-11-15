from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer

from megmis.common.schemas import LatLon, LocationInput
from megmis.engines.geo import GeoService
from megmis.engines.road import RoadService
from megmis.engines.routing import RoutingService
from megmis.engines.weather import WeatherService

weather = WeatherService()
geo = GeoService()
routing = RoutingService()
road = RoadService()

mcp = MCPServer(
    "mamiriro-megmis",
    version="0.1.0",
    instructions=(
        "Mamiriro (MEGMIS) intelligence tools for weather, geospatial, routing, "
        "and road conditions in Zimbabwe and beyond. Prefer named places or lat/lon. "
        "Every tool returns data plus provenance (data_source, confidence, official_vs_model)."
    ),
)


def _loc(
    location: dict[str, Any] | None = None,
    *,
    lat: float | None = None,
    lon: float | None = None,
    name: str | None = None,
) -> LocationInput:
    if location:
        return LocationInput(**location)
    return LocationInput(lat=lat, lon=lon, name=name)


def _dump(envelope: Any) -> dict[str, Any]:
    return envelope.model_dump(mode="json")


@mcp.tool()
def get_current_weather(location: dict[str, Any]) -> dict[str, Any]:
    """Current weather for a location ({lat,lon} or {name})."""
    return _dump(weather.current(_loc(location)))


@mcp.tool()
def get_forecast(location: dict[str, Any], days: int = 7) -> dict[str, Any]:
    """Daily forecast (1-14 days)."""
    return _dump(weather.forecast(_loc(location), days))


@mcp.tool()
def get_hourly_forecast(location: dict[str, Any], date: str) -> dict[str, Any]:
    """Hourly forecast for a specific ISO date (YYYY-MM-DD)."""
    from datetime import date as date_cls

    return _dump(weather.hourly(_loc(location), date_cls.fromisoformat(date)))


@mcp.tool()
def get_weather_alerts(location: dict[str, Any]) -> dict[str, Any]:
    """Active weather alerts; official warnings labelled separately from model-derived."""
    return _dump(weather.alerts(_loc(location)))


@mcp.tool()
def compare_weather(locations: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare current weather across multiple locations."""
    return _dump(weather.compare([_loc(loc) for loc in locations]))


@mcp.tool()
def get_historical_weather(
    location: dict[str, Any], start_date: str, end_date: str
) -> dict[str, Any]:
    """Historical weather observations between ISO dates."""
    from datetime import date as date_cls

    return _dump(
        weather.historical(
            _loc(location),
            date_cls.fromisoformat(start_date),
            date_cls.fromisoformat(end_date),
        )
    )


@mcp.tool()
def get_air_quality(location: dict[str, Any]) -> dict[str, Any]:
    """Air quality index and pollutants for a location."""
    return _dump(weather.air_quality(_loc(location)))


@mcp.tool()
def get_agricultural_conditions(location: dict[str, Any]) -> dict[str, Any]:
    """Agricultural / growing-condition indicators."""
    return _dump(weather.agricultural(_loc(location)))


@mcp.tool()
def analyze_weather_risk(
    location: dict[str, Any], activity: str, date: str | None = None
) -> dict[str, Any]:
    """Activity-based weather risk (e.g. outdoor_wedding) with recommendations."""
    from datetime import date as date_cls

    on = date_cls.fromisoformat(date) if date else None
    return _dump(weather.analyze_risk(_loc(location), activity, on))


@mcp.tool()
def recommend_outdoor_activities(
    location: dict[str, Any], date: str | None = None
) -> dict[str, Any]:
    """Suitability scores for common outdoor activities."""
    from datetime import date as date_cls

    on = date_cls.fromisoformat(date) if date else None
    return _dump(weather.recommend_activities(_loc(location), on))


@mcp.tool()
def geocode(address: str) -> dict[str, Any]:
    """Geocode an address or place name to coordinates."""
    return _dump(geo.geocode(address))


@mcp.tool()
def reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    """Reverse-geocode coordinates to an address."""
    return _dump(geo.reverse(lat, lon))


@mcp.tool()
def find_nearby_places(
    location: dict[str, Any], category: str | None = None, radius_m: int = 5000
) -> dict[str, Any]:
    """Find nearby places by optional category within radius_m."""
    return _dump(geo.nearby(_loc(location), category, radius_m))


@mcp.tool()
def get_emergency_facilities(
    location: dict[str, Any], type: str | None = None
) -> dict[str, Any]:
    """Nearby emergency facilities (hospital, police, fire)."""
    return _dump(geo.emergency(_loc(location), type))


@mcp.tool()
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
    return _dump(
        routing.optimize(
            _loc(origin),
            _loc(destination),
            waypoints=[_loc(w) for w in (waypoints or [])],
            profile=profile,
            vehicle_class=vehicle_class,
            departure_time=dep,
            priorities=priorities,
        )
    )


@mcp.tool()
def reroute(
    journey_id: str, current_position: dict[str, Any], reason: str = "conditions_changed"
) -> dict[str, Any]:
    """Recompute alternatives for an active journey."""
    return _dump(
        routing.reroute(
            journey_id,
            LatLon(lat=current_position["lat"], lon=current_position["lon"]),
            reason,
        )
    )


@mcp.tool()
def get_route_conditions(
    route_id: str | None = None, corridor: str | None = None
) -> dict[str, Any]:
    """Weather, traffic and road-condition summary for a route or corridor."""
    return _dump(routing.route_conditions(route_id=route_id, corridor=corridor))


@mcp.tool()
def report_road_condition(
    location: dict[str, Any],
    type: str,
    severity: int,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Submit a crowdsourced road-condition report."""
    return _dump(road.report(_loc(location), type, severity, evidence_refs))


@mcp.tool()
def get_road_incidents(
    area: str | None = None, corridor: str | None = None
) -> dict[str, Any]:
    """List road incidents for an area or corridor."""
    return _dump(road.incidents(area=area, corridor=corridor))


@mcp.tool()
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
    from megmis.common.auth import hash_api_key, lookup_api_key, seed_dev_key
    from megmis.common.tenant_ctx import get_tenant_context
    from megmis.config import get_settings
    from megmis.engines.risk import RiskService

    settings = get_settings()
    tenant_id: str | None = None
    ctx = get_tenant_context()
    if api_key:
        looked = lookup_api_key(hash_api_key(api_key))
        if looked:
            tenant_id = str(looked.tenant_id)
    elif ctx is not None:
        tenant_id = str(ctx.tenant_id)
    elif settings.use_persistence:
        # stdio / unauthenticated MCP: persist under seeded demo tenant
        demo = seed_dev_key(settings)
        tenant_id = str(demo.tenant_id)

    return _dump(
        RiskService().assess_journey(
            _loc(origin),
            _loc(destination),
            profile=profile,
            activity=activity,
            tenant_id=tenant_id,
        )
    )


@mcp.tool()
def get_traffic_congestion(corridor: str) -> dict[str, Any]:
    """Traffic sub-module congestion estimate for a corridor."""
    from megmis.engines.routing import traffic

    return {"data": traffic.get_congestion(corridor)}


@mcp.resource("weather://current/{location}")
def resource_current_weather(location: str) -> str:
    """Current weather resource for a named location."""
    return json.dumps(_dump(weather.current(LocationInput(name=location))), indent=2)


@mcp.resource("weather://forecast/{location}")
def resource_forecast(location: str) -> str:
    return json.dumps(_dump(weather.forecast(LocationInput(name=location))), indent=2)


@mcp.resource("weather://alerts/{location}")
def resource_alerts(location: str) -> str:
    return json.dumps(_dump(weather.alerts(LocationInput(name=location))), indent=2)


@mcp.resource("road://incidents/{area}")
def resource_incidents(area: str) -> str:
    return json.dumps(_dump(road.incidents(area=area)), indent=2)


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
        "(profile=safest). Explain trade-offs using cost_breakdown."
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
    return f"Analyse agricultural conditions near {location} using get_agricultural_conditions and get_forecast."


@mcp.prompt()
def plan_delivery_route(origin: str, destination: str, vehicle_class: str = "light_truck") -> str:
    return (
        f"Plan a delivery from {origin} to {destination} for vehicle_class={vehicle_class}. "
        "Use optimize_route with profile=fuel or safest and cite hazards."
    )


@mcp.prompt()
def prompt_assess_journey_risk(origin: str, destination: str) -> str:
    return (
        f"Assess end-to-end journey risk from {origin} to {destination}. "
        "Call assess_journey_risk tool; combine weather, road incidents and route explanations."
    )


def create_mcp_server() -> MCPServer:
    return mcp
