# Docker & Compose

## Images
- megmis-api      (FastAPI REST + MCP `/mcp`)
- megmis-worker   (async jobs: alerts, validation, webhook drain, graph refresh)
- megmis-console  (Gen 2 optional profile — proxies `/console` MVP)
Base images: python:3.12-slim, postgis/postgis:16-3.4, redis:7.

## Dockerfile conventions
Multi-stage: base -> prod. Non-root user. No secrets in images.

## compose topology (local)
services:
  api, worker,
  postgres (postgis), redis, minio,
  console (profile `console`),
  # optional later: valhalla / graphhopper profiles

```bash
docker compose up --build -d postgres redis api worker
docker compose --profile console up -d console   # http://localhost:8088/
```

API/worker set `USE_APP_ROLE=true` + `DATABASE_APP_URL` (role `megmis_app`, NOBYPASSRLS).
Migrations/seed still use owner `DATABASE_URL`.

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