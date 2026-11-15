"""Gen 4 Insurance / GovTech service packs — composed products over core engines."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from megmis.common.schemas import Confidence, Envelope, LocationInput, Provenance, new_request_id
from megmis.engines.risk.service import RiskService
from megmis.engines.road.service import RoadService
from megmis.engines.routing.service import RoutingService
from megmis.engines.weather.service import WeatherService

PACKS = {
    "insurance.corridor": {
        "name": "Insurance Corridor Pack",
        "description": "Journey risk + weather + road incidents for underwriting / telematics.",
        "scopes": ["risk:read", "weather:read", "road:read", "routing:read"],
        "vertical": "insurance",
    },
    "govtech.emergency": {
        "name": "GovTech Emergency Pack",
        "description": "Emergency facilities, corridor incidents, weather alerts for public ops.",
        "scopes": ["geo:read", "road:read", "weather:read"],
        "vertical": "govtech",
    },
    "govtech.mobility": {
        "name": "GovTech Mobility Pack",
        "description": "Explained routing + traffic + incident briefing for transport agencies.",
        "scopes": ["routing:read", "road:read", "traffic:read"],
        "vertical": "govtech",
    },
}


class PackService:
    def __init__(self) -> None:
        self.weather = WeatherService()
        self.routing = RoutingService()
        self.road = RoadService()
        self.risk = RiskService()

    def list_packs(self) -> list[dict[str, Any]]:
        return [{"id": k, **v} for k, v in PACKS.items()]

    def run_pack(
        self,
        pack_id: str,
        *,
        origin: LocationInput | None = None,
        destination: LocationInput | None = None,
        location: LocationInput | None = None,
        tenant_id: str | None = None,
        profile: str = "safest",
    ) -> Envelope[dict[str, Any]]:
        if pack_id not in PACKS:
            from megmis.common.errors import AppError

            raise AppError("NOT_FOUND", f"Unknown pack {pack_id}", status_code=404)

        meta = PACKS[pack_id]
        bundle: dict[str, Any] = {
            "pack_id": pack_id,
            "pack": meta,
            "ran_at": datetime.now(UTC).isoformat(),
            "run_id": str(uuid4()),
        }

        if pack_id == "insurance.corridor":
            if not origin or not destination:
                from megmis.common.errors import AppError

                raise AppError("INVALID_REQUEST", "origin and destination required", status_code=400)
            risk = self.risk.assess_journey(
                origin, destination, profile=profile, tenant_id=tenant_id, activity="road_trip"
            )
            route = self.routing.optimize(
                origin, destination, profile=profile, tenant_id=tenant_id
            )
            wx = self.weather.alerts(destination)
            corridor = f"{origin.name or 'origin'}-{destination.name or 'destination'}"
            incidents = self.road.incidents(corridor=corridor)
            bundle["sections"] = {
                "journey_risk": risk.data,
                "route": {
                    "route_id": (route.data or {}).get("route_id"),
                    "top": ((route.data or {}).get("routes") or [None])[0],
                    "profile": profile,
                },
                "weather_alerts": wx.data,
                "road_incidents": incidents.data,
            }
            bundle["summary"] = {
                "risk_level": (risk.data or {}).get("level"),
                "risk_score": (risk.data or {}).get("score"),
                "incident_count": len((incidents.data or {}).get("incidents") or []),
                "alert_count": len((wx.data or {}).get("alerts") or []),
            }

        elif pack_id == "govtech.emergency":
            loc = location or origin or LocationInput(name="Harare")
            from megmis.engines.geo.service import GeoService

            emergency = GeoService().emergency(loc)
            alerts = self.weather.alerts(loc)
            incidents = self.road.incidents(area=loc.name or "Harare")
            bundle["sections"] = {
                "emergency_facilities": emergency.data,
                "weather_alerts": alerts.data,
                "road_incidents": incidents.data,
            }
            bundle["summary"] = {
                "facilities": len((emergency.data or {}).get("facilities") or []),
                "alerts": len((alerts.data or {}).get("alerts") or []),
                "incidents": len((incidents.data or {}).get("incidents") or []),
            }

        else:  # govtech.mobility
            if not origin or not destination:
                from megmis.common.errors import AppError

                raise AppError("INVALID_REQUEST", "origin and destination required", status_code=400)
            route = self.routing.optimize(
                origin, destination, profile=profile, tenant_id=tenant_id
            )
            from megmis.engines.routing import traffic

            corridor = f"{origin.name or 'A'}-{destination.name or 'B'}"
            cong = traffic.get_congestion(corridor)
            incidents = self.road.incidents(corridor=corridor)
            bundle["sections"] = {
                "route": route.data,
                "traffic": cong,
                "road_incidents": incidents.data,
            }
            bundle["summary"] = {
                "alternatives": len((route.data or {}).get("routes") or []),
                "congestion": cong.get("congestion") if isinstance(cong, dict) else cong,
            }

        return Envelope(
            data=bundle,
            provenance=Provenance(data_source="packs", confidence=Confidence.medium),
            request_id=new_request_id(),
        )
