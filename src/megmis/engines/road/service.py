from __future__ import annotations

from typing import Any
from uuid import UUID

from megmis.common.schemas import (
    Confidence,
    Envelope,
    LocationInput,
    Provenance,
    new_request_id,
)
from megmis.config import get_settings
from megmis.db import repositories as repo
from megmis.db.session import session_scope
from megmis.engines.weather.service import WeatherService

# Seeded fallbacks used when DB has no incidents yet / persistence off
_FALLBACK_INCIDENTS: list[dict[str, Any]] = [
    {
        "id": "inc-flood-1",
        "type": "flood",
        "severity": 4,
        "confidence": 0.85,
        "verified": True,
        "geometry": {"lat": -19.2, "lon": 29.0},
        "area": "Harare-Bulawayo",
        "status": "active",
    },
    {
        "id": "inc-pothole-1",
        "type": "pothole",
        "severity": 2,
        "confidence": 0.25,
        "verified": False,
        "geometry": {"lat": -18.5, "lon": 31.5},
        "area": "Harare-Mutare",
        "status": "active",
    },
    {
        "id": "inc-damage-1",
        "type": "damaged_road",
        "severity": 3,
        "confidence": 0.7,
        "verified": False,
        "geometry": {"lat": -19.8, "lon": 29.5},
        "area": "Harare-Bulawayo",
        "status": "active",
    },
]


class RoadService:
    def __init__(self) -> None:
        self.weather = WeatherService()

    def _prov(self) -> Provenance:
        return Provenance(data_source="road-intelligence", confidence=Confidence.medium)

    def report(
        self,
        location: LocationInput,
        report_type: str,
        severity: int,
        evidence_refs: list[str] | None = None,
        tenant_id: str | None = None,
    ) -> Envelope[dict[str, Any]]:
        lat, lon, _ = self.weather.resolve_location(location)
        severity = max(1, min(5, severity))
        if get_settings().use_persistence and tenant_id:
            try:
                with session_scope(tenant_id=tenant_id) as session:
                    report = repo.add_road_report(
                        session,
                        tenant_id=UUID(tenant_id),
                        report_type=report_type,
                        severity=severity,
                        confidence=0.4,
                        lat=lat,
                        lon=lon,
                        area="custom",
                        evidence_refs=evidence_refs or [],
                    )
                    out = Envelope(
                        data={"report_id": str(report.id), "status": report.status},
                        provenance=self._prov(),
                        request_id=new_request_id(),
                    )
                try:
                    from megmis.api.v1.webhooks import deliver_event

                    deliver_event(
                        tenant_id,
                        "road.report",
                        {"report_id": out.data["report_id"], "type": report_type, "severity": severity},
                    )
                except Exception:
                    pass
                return out
            except Exception:
                pass

        from uuid import uuid4

        report_id = str(uuid4())
        _FALLBACK_INCIDENTS.append(
            {
                "id": report_id,
                "type": report_type,
                "severity": severity,
                "confidence": 0.4,
                "verified": False,
                "geometry": {"lat": lat, "lon": lon},
                "area": "custom",
                "status": "pending",
            }
        )
        return Envelope(
            data={"report_id": report_id, "status": "pending"},
            provenance=self._prov(),
            request_id=new_request_id(),
        )

    def incidents(
        self, area: str | None = None, corridor: str | None = None
    ) -> Envelope[dict[str, Any]]:
        key = (area or corridor or "").strip()
        items: list[dict[str, Any]] = []
        if get_settings().use_persistence:
            try:
                with session_scope(admin=True) as session:
                    rows = repo.list_incidents(session, area=key or None)
                    items = [
                        {
                            "id": str(r.id),
                            "type": r.type,
                            "severity": r.severity,
                            "confidence": r.confidence,
                            "verified": r.verified,
                            "geometry": {"lat": r.lat, "lon": r.lon},
                        }
                        for r in rows
                    ]
            except Exception:
                items = []

        if not items:
            key_l = key.lower()
            for r in _FALLBACK_INCIDENTS:
                if r.get("status") not in ("active", "pending", "verified"):
                    continue
                if key_l and key_l not in str(r.get("area", "")).lower():
                    continue
                items.append(
                    {
                        "id": r["id"],
                        "type": r["type"],
                        "severity": r["severity"],
                        "confidence": r["confidence"],
                        "verified": r.get("verified", False),
                        "geometry": r["geometry"],
                    }
                )

        return Envelope(data={"incidents": items}, provenance=self._prov(), request_id=new_request_id())
