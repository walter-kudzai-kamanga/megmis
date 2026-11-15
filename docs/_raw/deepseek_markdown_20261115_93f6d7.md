# Docker & Compose

## Images
- megmis-api      (FastAPI REST)
- megmis-mcp      (MCP server; thin adapter)
- megmis-worker   (async jobs: alerts, validation, graph refresh)
- megmis-console  (Phase 2; optional)
Base images: python:3.12-slim, postgis/postgis:16-3.4, redis:7.

## Dockerfile conventions
Multi-stage: base -> dev -> test -> prod. Non-root user. Pin digests. No secrets.

## compose topology (local)
services:
  api, mcp, worker,
  postgres (postgis), redis, minio,
  mock-providers (weather/routing/geocode/speech),
  valhalla (optional profile), graphhopper (optional profile)

## Volumes
valhalla_data, graphhopper_data, minio_data, pg_data.

## Env (.env.example)
DATABASE_URL, REDIS_URL, S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY,
WEATHER_PROVIDER, ROUTING_PROVIDER, GEOCODE_PROVIDER, SPEECH_PROVIDER,
OPEN_METEO_BASE_URL, OPENWEATHER_KEY, VALHALLA_URL, GRAPHHOPPER_URL,
MCP_TRANSPORT, LOG_LEVEL, APP_ENV

## Healthchecks
api /healthz, mcp /healthz, postgres pg_isready, redis ping.
depends_on with condition: service_healthy.