# MCP Tool Contracts

Handlers stay thin (validate, authorise, delegate, format). Each tool maps to one
owning service (see service-catalogue.md). Errors use the shared Error schema.

## Common envelope
Every response: { data, provenance{data_source, confidence, retrieved_at,
official_vs_model}, request_id }

## Tools

### get_current_weather
Input:  { location: {lat,lon} | {name} }
Output: { condition, temperature_c, humidity, wind, precipitation, provenance }
Errors: INVALID_LOCATION, PROVIDER_UNAVAILABLE

### get_forecast
Input:  { location, days: int(1..14) }
Output: { daily: [ {date, min, max, condition, precipitation_prob, provenance} ] }

### get_hourly_forecast
Input:  { location, date }
Output: { hourly: [ {time, temp, precip_prob, wind} ] }

### get_weather_alerts
Input:  { location }
Output: { alerts: [ {type, severity, source, official: bool, valid_from, valid_to} ] }
Note: official warnings and model-derived alerts labelled separately.

### compare_weather
Input:  { locations: [location] }
Output: { comparison: [ {location, summary} ] }

### get_historical_weather
Input:  { location, start_date, end_date }
Output: { records: [ {date, observations} ] }

### get_air_quality
Input:  { location }
Output: { aqi, pollutants, provenance }

### get_agricultural_conditions
Input:  { location }
Output: { rainfall_mm, humidity, soil_moisture (nullable), growing_conditions }

### analyze_weather_risk
Input:  { location, activity, date }
Output: { weather_assessment, recommendations[], confidence }
(Golden example: spec Section 7.4.)

### recommend_outdoor_activities
Input:  { location, date }
Output: { recommendations: [ {activity, suitability, reasons[]} ] }

### geocode / reverse_geocode
Input:  { address } | { lat, lon }
Output: { lat, lon } | { address, components }

### find_nearby_places
Input:  { location, category, radius_m }
Output: { places: [ {name, category, lat, lon, distance_m} ] }

### optimize_route
Input:  { origin, destination, waypoints[], vehicle_class, priorities[], departure_time }
Output: { routes: [ {rank, distance_m, duration_s, hazards[], cost_breakdown[],
explanation} ] }

### reroute
Input:  { journey_id, current_position, reason }
Output: { alternatives: [ route ] }

### get_route_conditions
Input:  { route_id | corridor }
Output: { weather_summary, traffic_summary, road_condition_summary }

### report_road_condition
Input:  { location, type, severity, evidence_refs[]? }
Output: { report_id, status }

### get_road_incidents
Input:  { area | corridor }
Output: { incidents: [ {id, type, severity, confidence, verified, geometry} ] }

### get_emergency_facilities
Input:  { location, type }
Output: { facilities: [ {name, type, contact, lat, lon} ] }

## Resources
weather://current/{location}, weather://forecast/{location},
weather://alerts/{location}, weather://historical/{location},
road://incidents/{area}, route://journey/{journey_id}

## Prompts
plan_trip, assess_weather_risk, prepare_outdoor_event,
analyze_agricultural_conditions, plan_delivery_route, assess_journey_risk

## Discovery/auth ordering
Protocol-level capability negotiation at connect; tenant-scoped tool visibility
only after auth completes. No tenant-specific tool listed pre-auth.

## Versioning
Tool schema versioned in `x-mcp-version`; breaking changes require new tool name.