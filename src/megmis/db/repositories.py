from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from megmis.db.models import Incident, Journey, Location, RoadReport, Route, Tenant


def point_wkt(lon: float, lat: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


def get_or_create_location(
    session: Session,
    *,
    name: str,
    lat: float,
    lon: float,
    tenant_id: uuid.UUID | None = None,
    admin_area: str | None = "Zimbabwe",
) -> Location:
    stmt = select(Location).where(Location.name == name)
    if tenant_id is None:
        stmt = stmt.where(Location.tenant_id.is_(None))
    else:
        stmt = stmt.where(Location.tenant_id == tenant_id)
    existing = session.scalar(stmt)
    if existing:
        return existing
    loc = Location(
        tenant_id=tenant_id,
        name=name,
        lat=lat,
        lon=lon,
        geom=point_wkt(lon, lat),
        admin_area=admin_area,
    )
    session.add(loc)
    session.flush()
    return loc


def save_route(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    profile: str,
    vehicle_class: str,
    origin: dict[str, float],
    destination: dict[str, float],
    waypoints: list[dict[str, Any]],
    result: dict[str, Any],
    departure_time: datetime | None = None,
) -> Route:
    origin_loc = get_or_create_location(
        session,
        name=f"pt:{origin['lat']:.4f},{origin['lon']:.4f}",
        lat=origin["lat"],
        lon=origin["lon"],
        tenant_id=tenant_id,
    )
    dest_loc = get_or_create_location(
        session,
        name=f"pt:{destination['lat']:.4f},{destination['lon']:.4f}",
        lat=destination["lat"],
        lon=destination["lon"],
        tenant_id=tenant_id,
    )
    route = Route(
        tenant_id=tenant_id,
        origin_location_id=origin_loc.id,
        destination_location_id=dest_loc.id,
        waypoints=waypoints,
        profile=profile,
        vehicle_class=vehicle_class,
        departure_time=departure_time,
        result=result,
    )
    session.add(route)
    session.flush()
    result["route_id"] = str(route.id)
    route.result = result
    session.flush()
    return route


def get_route(session: Session, route_id: str, tenant_id: uuid.UUID | None = None) -> Route | None:
    try:
        rid = uuid.UUID(route_id)
    except ValueError:
        return None
    stmt = select(Route).where(Route.id == rid)
    if tenant_id is not None:
        stmt = stmt.where(Route.tenant_id == tenant_id)
    return session.scalar(stmt)


def create_journey(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    route: Route,
) -> Journey:
    origin = route.result.get("origin", {})
    journey = Journey(
        tenant_id=tenant_id,
        route_id=route.id,
        status="active",
        current_lat=origin.get("lat"),
        current_lon=origin.get("lon"),
        current_position=point_wkt(origin["lon"], origin["lat"])
        if origin.get("lat") is not None
        else None,
        snapshot={
            "profile": route.profile,
            "vehicle_class": route.vehicle_class,
            "origin": route.result.get("origin"),
            "destination": route.result.get("destination"),
            "monitored_route": (route.result.get("routes") or [])[:1],
        },
    )
    session.add(journey)
    session.flush()
    return journey


def get_journey(
    session: Session, journey_id: str, tenant_id: uuid.UUID
) -> Journey | None:
    try:
        jid = uuid.UUID(journey_id)
    except ValueError:
        return None
    return session.scalar(
        select(Journey).where(Journey.id == jid, Journey.tenant_id == tenant_id)
    )


def add_road_report(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    report_type: str,
    severity: int,
    confidence: float,
    lat: float,
    lon: float,
    area: str | None,
    evidence_refs: list[str],
) -> RoadReport:
    from datetime import UTC, datetime, timedelta

    expiry_days = {
        "pothole": 30,
        "closure": None,
        "flood": 7,
        "accident": 3,
        "damaged_road": 30,
    }.get(report_type, 30)
    expires = None if expiry_days is None else datetime.now(UTC) + timedelta(days=expiry_days)
    report = RoadReport(
        tenant_id=tenant_id,
        type=report_type,
        severity=severity,
        confidence=confidence,
        status="pending",
        evidence_refs=evidence_refs,
        area=area or "custom",
        lat=lat,
        lon=lon,
        reporter_ref=f"anon-{uuid.uuid4().hex[:8]}",
        expires_at=expires,
    )
    session.add(report)
    session.flush()
    return report


def list_incidents(session: Session, *, area: str | None = None) -> list[Incident]:
    stmt = select(Incident).where(Incident.status.in_(["active", "pending", "verified"]))
    if area:
        stmt = stmt.where(Incident.area.ilike(f"%{area}%"))
    return list(session.scalars(stmt).all())


def ensure_tenant(session: Session, slug: str, name: str) -> Tenant:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant:
        return tenant
    tenant = Tenant(name=name, slug=slug, plan="pro", status="active", settings={})
    session.add(tenant)
    session.flush()
    return tenant
