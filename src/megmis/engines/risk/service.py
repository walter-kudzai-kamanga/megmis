from __future__ import annotations

from typing import Any
from uuid import UUID

from megmis.common.errors import AppError
from megmis.common.schemas import (
    Confidence,
    Envelope,
    LocationInput,
    OfficialVsModel,
    Provenance,
    new_request_id,
)
from megmis.config import get_settings
from megmis.db.models import RiskAssessment
from megmis.db.session import session_scope
from megmis.engines.road.service import RoadService
from megmis.engines.routing.service import RoutingService
from megmis.engines.weather.service import WeatherService


class RiskService:
    """Journey Risk Assessment — composes weather + routing + road; persists assessments."""

    def __init__(self) -> None:
        self.weather = WeatherService()
        self.routing = RoutingService()
        self.road = RoadService()

    def assess_journey(
        self,
        origin: LocationInput,
        destination: LocationInput,
        profile: str = "safest",
        tenant_id: str | None = None,
        activity: str | None = "road_trip",
    ) -> Envelope[dict[str, Any]]:
        route = self.routing.optimize(
            origin, destination, profile=profile, tenant_id=tenant_id
        )
        weather_o = self.weather.current(origin)
        weather_d = self.weather.current(destination)
        incidents = self.road.incidents(corridor="Harare-Bulawayo")

        top = route.data["routes"][0] if route.data["routes"] else None
        hazard_count = len(top["hazards"]) if top else 0
        incident_count = len(incidents.data["incidents"])
        score = min(1.0, 0.2 + 0.15 * hazard_count + 0.05 * incident_count)
        level = "high" if score >= 0.7 else "moderate" if score >= 0.4 else "low"

        data = {
            "score": round(score, 2),
            "level": level,
            "activity": activity,
            "indicators": {
                "origin_weather": weather_o.data.get("condition"),
                "destination_weather": weather_d.data.get("condition"),
                "top_route_hazards": top["hazards"] if top else [],
                "incident_count": incident_count,
            },
            "recommendations": [
                top["explanation"] if top else "No route available",
                "Monitor official weather warnings along the corridor.",
            ],
            "route": route.data,
            "data_sources": ["weather", "routing", "road"],
        }

        if get_settings().use_persistence and tenant_id:
            try:
                with session_scope(tenant_id=tenant_id) as session:
                    row = RiskAssessment(
                        tenant_id=UUID(tenant_id),
                        subject_type="journey",
                        subject_id=route.data.get("route_id", "unknown"),
                        activity=activity,
                        score=data["score"],
                        level=level,
                        indicators=data["indicators"],
                        recommendations=data["recommendations"],
                        confidence="medium",
                        data_sources=data["data_sources"],
                    )
                    session.add(row)
                    session.flush()
                    data["assessment_id"] = str(row.id)
            except Exception:
                pass

        return Envelope(
            data=data,
            provenance=Provenance(
                data_source="journey-risk",
                confidence=Confidence.medium,
                official_vs_model=OfficialVsModel.mixed,
            ),
            request_id=new_request_id(),
        )

    def get_assessment(self, assessment_id: str, tenant_id: str) -> Envelope[dict[str, Any]]:
        with session_scope(tenant_id=tenant_id) as session:
            row = session.get(RiskAssessment, UUID(assessment_id))
            if row is None or str(row.tenant_id) != tenant_id:
                raise AppError("NOT_FOUND", "Assessment not found", status_code=404)
            data = {
                "assessment_id": str(row.id),
                "score": row.score,
                "level": row.level,
                "activity": row.activity,
                "indicators": row.indicators,
                "recommendations": row.recommendations,
                "data_sources": row.data_sources,
                "subject_type": row.subject_type,
                "subject_id": row.subject_id,
            }
        return Envelope(
            data=data,
            provenance=Provenance(
                data_source="journey-risk",
                confidence=Confidence.medium,
                official_vs_model=OfficialVsModel.mixed,
            ),
            request_id=new_request_id(),
        )
