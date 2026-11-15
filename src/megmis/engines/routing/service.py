from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from megmis.common.errors import AppError
from megmis.common.schemas import (
    Confidence,
    Envelope,
    LatLon,
    LocationInput,
    Provenance,
    new_request_id,
)
from megmis.config import get_settings
from megmis.db import repositories as repo
from megmis.db.redis_cache import journey_state_set, route_cache_get, route_cache_set
from megmis.db.session import session_scope
from megmis.engines.geo.service import GeoService
from megmis.engines.routing.cost_model import score_candidate
from megmis.engines.weather.service import WeatherService
from megmis.providers.factory import get_routing_provider

# Fallback when USE_PERSISTENCE=false or DB unavailable
_ROUTES: dict[str, dict[str, Any]] = {}
_JOURNEYS: dict[str, dict[str, Any]] = {}


class RoutingService:
    def __init__(self, tenant_id: UUID | None = None) -> None:
        self.routing = get_routing_provider()
        self.geo = GeoService()
        self.weather = WeatherService()
        self.tenant_id = tenant_id

    def _prov(self) -> Provenance:
        return Provenance(
            data_source=getattr(self.routing, "name", "routing"),
            confidence=Confidence.medium,
        )

    def _persist_enabled(self) -> bool:
        return get_settings().use_persistence

    def optimize(
        self,
        origin: LocationInput,
        destination: LocationInput,
        *,
        waypoints: list[LocationInput] | None = None,
        profile: str = "safest",
        vehicle_class: str = "car",
        departure_time: datetime | None = None,
        priorities: list[str] | None = None,
        tenant_id: str | None = None,
    ) -> Envelope[dict[str, Any]]:
        if priorities:
            joined = " ".join(priorities).lower()
            if "safe" in joined:
                profile = "safest"
            elif "fast" in joined:
                profile = "fastest"
            elif "fuel" in joined:
                profile = "fuel"
            elif "cheap" in joined:
                profile = "cheapest"

        o = self.geo.resolve_latlon(origin)
        d = self.geo.resolve_latlon(destination)
        wps = [self.geo.resolve_latlon(w) for w in (waypoints or [])]

        cache_payload = {
            "origin": o.model_dump(),
            "destination": d.model_dump(),
            "waypoints": [w.model_dump() for w in wps],
            "vehicle_class": vehicle_class,
        }
        if self._persist_enabled():
            cached = route_cache_get(cache_payload, profile)
            if cached:
                return Envelope(data=cached, provenance=self._prov(), request_id=new_request_id())

        candidates = self.routing.route(o, d, wps, profile, departure_time)
        scored = [score_candidate(c, profile, vehicle_class) for c in candidates]
        scored = [s for s in scored if not s["closed"]]
        scored.sort(key=lambda s: s["cost"] if s["cost"] is not None else 1e9)
        for i, s in enumerate(scored, start=1):
            s["rank"] = i

        result = {
            "profile": profile,
            "vehicle_class": vehicle_class,
            "origin": o.model_dump(),
            "destination": d.model_dump(),
            "routes": scored,
        }

        tid = tenant_id or (str(self.tenant_id) if self.tenant_id else None)
        if self._persist_enabled() and tid:
            try:
                with session_scope(tenant_id=tid) as session:
                    route = repo.save_route(
                        session,
                        tenant_id=UUID(tid),
                        profile=profile,
                        vehicle_class=vehicle_class,
                        origin=o.model_dump(),
                        destination=d.model_dump(),
                        waypoints=[w.model_dump() for w in wps],
                        result=result,
                        departure_time=departure_time,
                    )
                    result = dict(route.result)
            except Exception:
                result["route_id"] = str(uuid4())
                _ROUTES[result["route_id"]] = result
        else:
            result["route_id"] = str(uuid4())
            _ROUTES[result["route_id"]] = result

        if self._persist_enabled():
            route_cache_set(cache_payload, profile, result)
        return Envelope(data=result, provenance=self._prov(), request_id=new_request_id())

    def reroute(
        self,
        journey_id: str,
        current_position: LatLon,
        reason: str,
        tenant_id: str | None = None,
    ) -> Envelope[dict[str, Any]]:
        journey = self._load_journey(journey_id, tenant_id)
        if not journey:
            raise AppError("NOT_FOUND", f"Journey {journey_id} not found", status_code=404)
        dest = LocationInput(**journey["destination"])
        result = self.optimize(
            LocationInput(lat=current_position.lat, lon=current_position.lon),
            dest,
            profile=journey.get("profile", "safest"),
            vehicle_class=journey.get("vehicle_class", "car"),
            tenant_id=tenant_id,
        )
        return Envelope(
            data={"alternatives": result.data["routes"], "reason": reason},
            provenance=self._prov(),
            request_id=new_request_id(),
        )

    def route_conditions(
        self, route_id: str | None = None, corridor: str | None = None, tenant_id: str | None = None
    ) -> Envelope[dict[str, Any]]:
        from megmis.engines.road.service import RoadService
        from megmis.engines.routing import traffic

        route = self._load_route(route_id or "", tenant_id)
        loc = LocationInput(name="Harare")
        if route:
            loc = LocationInput(**route["origin"])
        weather = self.weather.current(loc)
        road = RoadService().incidents(area=corridor or "Harare-Bulawayo")
        cong = traffic.get_congestion(corridor or "A1 Harare")
        data = {
            "weather_summary": {
                "condition": weather.data.get("condition"),
                "temperature_c": weather.data.get("temperature_c"),
            },
            "traffic_summary": cong,
            "road_condition_summary": {
                "incident_count": len(road.data.get("incidents", [])),
                "incidents": road.data.get("incidents", [])[:5],
            },
        }
        return Envelope(data=data, provenance=self._prov(), request_id=new_request_id())

    def create_journey(self, route_id: str, tenant_id: str) -> Envelope[dict[str, Any]]:
        if self._persist_enabled():
            try:
                with session_scope(tenant_id=tenant_id) as session:
                    route = repo.get_route(session, route_id, UUID(tenant_id))
                    if route is None:
                        raise AppError("NOT_FOUND", f"Route {route_id} not found", status_code=404)
                    journey = repo.create_journey(
                        session, tenant_id=UUID(tenant_id), route=route
                    )
                    data = {
                        "id": str(journey.id),
                        "tenant_id": tenant_id,
                        "route_id": route_id,
                        "status": journey.status,
                        "profile": route.profile,
                        "vehicle_class": route.vehicle_class,
                        "origin": route.result.get("origin"),
                        "destination": route.result.get("destination"),
                        "current_position": {
                            "lat": journey.current_lat,
                            "lon": journey.current_lon,
                        },
                        "monitored_route": journey.snapshot.get("monitored_route"),
                    }
                    journey_state_set(str(journey.id), data)
                    return Envelope(data=data, provenance=self._prov(), request_id=new_request_id())
            except AppError:
                raise
            except Exception:
                pass

        route = _ROUTES.get(route_id)
        if not route:
            raise AppError("NOT_FOUND", f"Route {route_id} not found", status_code=404)
        journey_id = str(uuid4())
        journey = {
            "id": journey_id,
            "tenant_id": tenant_id,
            "route_id": route_id,
            "status": "active",
            "profile": route.get("profile"),
            "vehicle_class": route.get("vehicle_class"),
            "origin": route["origin"],
            "destination": route["destination"],
            "current_position": route["origin"],
            "monitored_route": route["routes"][:1],
        }
        _JOURNEYS[journey_id] = journey
        journey_state_set(journey_id, journey)
        return Envelope(data=journey, provenance=self._prov(), request_id=new_request_id())

    def get_journey(self, journey_id: str, tenant_id: str) -> Envelope[dict[str, Any]]:
        journey = self._load_journey(journey_id, tenant_id)
        if not journey:
            raise AppError("NOT_FOUND", f"Journey {journey_id} not found", status_code=404)
        return Envelope(data=journey, provenance=self._prov(), request_id=new_request_id())

    def _load_route(self, route_id: str, tenant_id: str | None) -> dict[str, Any] | None:
        if not route_id:
            return None
        if self._persist_enabled() and tenant_id:
            try:
                with session_scope(tenant_id=tenant_id) as session:
                    route = repo.get_route(session, route_id, UUID(tenant_id))
                    if route:
                        return dict(route.result)
            except Exception:
                pass
        return _ROUTES.get(route_id)

    def _load_journey(self, journey_id: str, tenant_id: str | None) -> dict[str, Any] | None:
        if self._persist_enabled() and tenant_id:
            try:
                with session_scope(tenant_id=tenant_id) as session:
                    journey = repo.get_journey(session, journey_id, UUID(tenant_id))
                    if journey:
                        return {
                            "id": str(journey.id),
                            "tenant_id": str(journey.tenant_id),
                            "route_id": str(journey.route_id),
                            "status": journey.status,
                            "profile": journey.snapshot.get("profile"),
                            "vehicle_class": journey.snapshot.get("vehicle_class"),
                            "origin": journey.snapshot.get("origin"),
                            "destination": journey.snapshot.get("destination"),
                            "current_position": {
                                "lat": journey.current_lat,
                                "lon": journey.current_lon,
                            },
                            "monitored_route": journey.snapshot.get("monitored_route"),
                        }
                    return None
            except Exception:
                pass
        journey = _JOURNEYS.get(journey_id)
        if not journey or (tenant_id and journey.get("tenant_id") != tenant_id):
            return None
        return journey
