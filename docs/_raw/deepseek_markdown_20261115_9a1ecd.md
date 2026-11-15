# Mamiriro Service Catalogue (Canonical)

This is the single authoritative service list. Figure 1, Section 4.2 and Figure 2
must be aligned to it.

## Services

| Service | Responsibility | Sync/Async | Interfaces | Owns data |
|---|---|---|---|---|
| Weather Intelligence | current, forecast, hourly, alerts, historical, air quality, agricultural, weather risk | sync + async (alerts) | REST, MCP | weather_cache, weather_snapshots |
| Geospatial Intelligence | geocode, reverse geocode, nearby places, distance/bbox/corridor queries | sync | REST, MCP | places_cache, geocode_cache |
| Routing & Optimization (incl. Traffic sub-module) | route calc, alternatives, reroute, vehicle profiles, traffic-aware costing | sync + async (reroute) | REST, MCP, WebSocket | route_cache, journeys |
| Road & Incident Intelligence | crowdsourced reports, incidents, validation, confidence, expiry | sync + async (validation) | REST, MCP, webhooks | road_reports, incidents |
| Journey Risk Assessment | composes weather+geo+routing+road to score journey risk | sync | REST, MCP | risk_assessments |
| Voice Intelligence | STT/TTS, agent sessions, tele-agent orchestration | async (WebRTC/WS) | REST, WebSocket, WebRTC, MCP (as client) | agent_sessions, audio_artefacts |

## Traffic sub-module (ADR-002)
- Part of Routing & Optimization.
- Interface: `traffic.get_congestion(corridor)`, `traffic.estimate_time(edge, at_time)`.
- Extraction seam documented; not a separate service in Phase 1.

## Tool/endpoint ownership map

| MCP tool | REST endpoint | Owning service |
|---|---|---|
| get_current_weather | GET /api/v1/weather/current | Weather |
| get_forecast | GET /api/v1/weather/forecast | Weather |
| get_hourly_forecast | GET /api/v1/weather/forecast?hourly=true | Weather |
| get_weather_alerts | GET /api/v1/weather/alerts | Weather |
| compare_weather | GET /api/v1/weather/compare | Weather |
| get_historical_weather | GET /api/v1/weather/historical | Weather |
| get_air_quality | GET /api/v1/weather/air-quality | Weather |
| get_agricultural_conditions | GET /api/v1/weather/agricultural | Weather |
| analyze_weather_risk | POST /api/v1/weather/risk | Weather |
| recommend_outdoor_activities | POST /api/v1/weather/activities | Weather |
| geocode / reverse geocode | GET /api/v1/geo/geocode | Geospatial |
| find_nearby_places | GET /api/v1/geo/nearby | Geospatial |
| optimize_route | POST /api/v1/routes/optimize | Routing & Optimization |
| reroute | POST /api/v1/routes/reroute | Routing & Optimization |
| get_route_conditions | GET /api/v1/routes/{id}/conditions | Routing & Optimization (+ Weather + Road) |
| report_road_condition | POST /api/v1/roads/reports | Road & Incident |
| get_road_incidents | GET /api/v1/roads/incidents | Road & Incident |
| get_emergency_facilities | GET /api/v1/geo/emergency | Geospatial |
| (composite) | POST /api/v1/journeys, GET /api/v1/journeys/{id} | Journey Risk Assessment |
| (composite) | POST /api/v1/agents/sessions | Voice Intelligence |

## Dependency graph
Weather -> (none)
Geospatial -> (none)
Road & Incident -> (none)
Routing & Optimization -> Road & Incident (costs), Weather (time-of-arrival), Traffic (internal)
Journey Risk -> Weather, Geospatial, Routing, Road & Incident
Voice Intelligence -> MCP clients of all of the above