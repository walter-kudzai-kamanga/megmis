from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from geoalchemy2.elements import WKTElement
from sqlalchemy import select

from megmis.db.models import Incident, RoadReport
from megmis.db.session import session_scope

# Retention / expiry by report type (days); closure waits until cleared
EXPIRY_DAYS = {
    "pothole": 30,
    "poor_surface": 30,
    "construction": 14,
    "accident": 3,
    "flood": 7,
    "damaged_bridge": 60,
    "damaged_road": 30,
    "closure": None,  # until cleared
}

# Corroboration distance threshold (degrees ~1km at equator ~0.01)
NEAR_DEG = 0.01


def validate_pending_reports(limit: int = 100) -> dict[str, Any]:
    """Worker job: validate pending reports, boost confidence, expire stale, create incidents."""
    now = datetime.now(UTC)
    validated = 0
    expired = 0
    incidents_created = 0
    corroborated = 0

    with session_scope(admin=True) as session:
        pending = list(
            session.scalars(
                select(RoadReport)
                .where(RoadReport.status == "pending")
                .limit(limit)
            ).all()
        )
        for report in pending:
            # Expiry
            days = EXPIRY_DAYS.get(report.type, 30)
            if days is not None:
                report.expires_at = report.reported_at + timedelta(days=days) if report.reported_at else now + timedelta(days=days)
                if report.expires_at and report.expires_at < now:
                    report.status = "expired"
                    expired += 1
                    continue

            # Corroboration: nearby same-type reports
            nearby = []
            if report.lat is not None and report.lon is not None:
                nearby = list(
                    session.scalars(
                        select(RoadReport).where(
                            RoadReport.id != report.id,
                            RoadReport.type == report.type,
                            RoadReport.status.in_(["pending", "verified", "active"]),
                        )
                    ).all()
                )
                nearby = [
                    r
                    for r in nearby
                    if r.lat is not None
                    and r.lon is not None
                    and abs(r.lat - report.lat) < NEAR_DEG
                    and abs(r.lon - report.lon) < NEAR_DEG
                ]
            report.corroboration_count = len(nearby)
            if nearby:
                corroborated += 1
                report.confidence = min(1.0, float(report.confidence or 0.4) + 0.15 * len(nearby))

            # Validation rules
            notes = []
            if report.severity and report.severity >= 4 and (report.confidence or 0) >= 0.6:
                report.status = "verified"
                notes.append("high severity + confidence auto-verified")
            elif (report.confidence or 0) >= 0.75:
                report.status = "verified"
                notes.append("confidence threshold met")
            else:
                report.status = "active"
                notes.append("accepted pending further corroboration")

            # Low confidence never becomes verified closure
            if report.type == "closure" and (report.confidence or 0) < 0.3:
                report.status = "active"
                notes.append("low-confidence closure not verified")

            report.validated_at = now
            report.validation_notes = "; ".join(notes)
            validated += 1

            if report.status in {"verified", "active"} and (report.confidence or 0) >= 0.3:
                inc = Incident(
                    source="crowdsourced",
                    road_report_id=report.id,
                    type=report.type,
                    severity=report.severity or 1,
                    confidence=report.confidence or 0.4,
                    status="active",
                    area=report.area,
                    lat=report.lat,
                    lon=report.lon,
                    verified=report.status == "verified",
                    valid_from=now,
                    valid_to=report.expires_at,
                    geom=WKTElement(f"POINT({report.lon} {report.lat})", srid=4326)
                    if report.lat is not None and report.lon is not None
                    else None,
                )
                session.add(inc)
                incidents_created += 1

        # Expire old active incidents past valid_to
        active = list(session.scalars(select(Incident).where(Incident.status == "active")).all())
        for inc in active:
            if inc.valid_to and inc.valid_to < now:
                inc.status = "expired"
                expired += 1

    return {
        "validated": validated,
        "expired": expired,
        "incidents_created": incidents_created,
        "corroborated": corroborated,
    }


def expire_reports_for_tenant(tenant_id: str) -> int:
    now = datetime.now(UTC)
    count = 0
    with session_scope(tenant_id=tenant_id) as session:
        rows = list(
            session.scalars(
                select(RoadReport).where(
                    RoadReport.tenant_id == UUID(tenant_id),
                    RoadReport.status.in_(["pending", "active", "verified"]),
                )
            ).all()
        )
        for r in rows:
            if r.expires_at and r.expires_at < now:
                r.status = "expired"
                count += 1
    return count
