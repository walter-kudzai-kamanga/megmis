# Domain Model

## Entities

### Tenant
id (uuid), name, slug, plan, status, created_at, settings (jsonb)

### ApiKey
id, tenant_id, hashed_key, prefix, scopes[], label, last_used_at, expires_at, revoked_at

### Location
id, tenant_id (nullable for shared), name, lat, lon, geometry (Point, 4326), admin_area

### Route
id, tenant_id, origin_location_id, destination_location_id, waypoints (jsonb),
profile (fastest|safest|cheapest|fuel), vehicle_class, departure_time,
result (jsonb: ranked alternatives with explanation), created_at

### Journey
id, tenant_id, route_id, status (active|completed|cancelled), current_position,
monitored_route (LineString), alert_subscriptions (jsonb), created_at, updated_at

### RoadReport
id, tenant_id, location_id, type (pothole|flood|accident|closure|damaged_bridge|
poor_surface|construction), severity (1-5), confidence (0-1), status
(pending|verified|expired|cleared), reporter_ref (pseudonymous), evidence_refs[],
reported_at, expires_at, corroboration_count

### Incident
id, source (crowdsourced|external), road_report_id (nullable), geometry,
type, severity, confidence, valid_from, valid_to, status

### WeatherSnapshot
id, location_id, provider, observed_at, payload (jsonb), is_official_warning (bool)

### RiskAssessment
id, tenant_id, subject_type (journey|location|activity), subject_id, activity,
score, level, indicators (jsonb), recommendations (jsonb), confidence, data_sources[]

### AgentSession
id, tenant_id, channel (voice|text), state, transcript_ref, started_at, ended_at

## Cross-cutting conventions (Section 7.5)
Every response includes: `units` (metric), `timestamps` (ISO-8601 UTC + local),
`data_source`, `confidence`, and where applicable `official_vs_model` label.

## Error model
{ "code": "MACHINE_CODE", "message": "human readable", "details": {...}, "request_id": "..." }