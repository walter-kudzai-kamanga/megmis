# Operations Runbook

## Environments
local (compose) -> staging -> production (managed Postgres + container platform;
K8s path documented for scale-out).

## Backups
PostGIS: nightly base + WAL archiving; restore drill monthly.
Object storage: versioning on.

## Routing graph refresh
Valhalla/GraphHopper graph rebuilt on OSM extract schedule; blue/green graph
volume swap; health-gated.

## Provider failover
Weather: Open-Meteo -> OpenWeather on repeated failures. Routing: Valhalla ->
GraphHopper/OSRM -> Google Routes (benchmark). Speech: configured fallback.
Failover logged as metric and alert.

## Incidents
- Tenant isolation suspicion: revoke keys, enable query audit, page security.
- Provider outage: switch config, confirm cache serves stale within TTL.
- RLS misconfig: app role must be non-BYPASSRLS; verify at startup.

## Capacity assumptions (initial)
50 tenants, 1M requests/day, Zimbabwe graph, single region.

## On-call
Pager for provider down, error budget burn, auth failures spike, RLS violations.