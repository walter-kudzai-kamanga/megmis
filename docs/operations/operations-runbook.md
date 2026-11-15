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

## Provider failover (Gen 4)
Health-gated switch via `ProviderOrchestrator` (`GET /api/v1/ops/providers`,
`POST /api/v1/ops/providers/probe`). Chains from env:
`WEATHER_FAILOVER`, `ROUTING_FAILOVER`, `GEOCODE_FAILOVER`, `SPEECH_FAILOVER`.
After `failure_threshold` consecutive failures the primary cools down and traffic
moves to the next healthy name. Failovers increment `provider_failover_count`
and fire alert hooks.

**Open-Meteo licence gate:** free Open-Meteo is non-commercial. Leave
`OPEN_METEO_COMMERCIAL_OK=false` until licensed; prod with
`WEATHER_PROVIDER=open-meteo` falls back / reports
`checks.open_meteo_licence=blocked_non_commercial` on `/healthz`.

## Object storage retention (Gen 4)
`OBJECT_STORE_BACKEND=local|s3`. Voice audio + evidence blobs carry
`AUDIO_RETENTION_DAYS` / `EVIDENCE_RETENTION_DAYS`. Worker job
`object_retention` purges expired keys; manual `POST /api/v1/ops/storage/purge`.

## Incidents
- Tenant isolation suspicion: revoke keys, enable query audit, page security.
- Provider outage: switch config, confirm cache serves stale within TTL.
- RLS misconfig: app role must be non-BYPASSRLS; verify at startup.

## Capacity assumptions (initial)
50 tenants, 1M requests/day, Zimbabwe graph, single region.

## On-call
Pager for provider down, error budget burn, auth failures spike, RLS violations.