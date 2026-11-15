# Mamiriro (MEGMIS)

**Mamiriro Environmental, Geospatial & Mobility Intelligence Server** — multi-tenant weather, geospatial, routing, road-condition, and journey-risk intelligence exposed via **FastAPI (REST)** and **MCP** (stdio + Streamable HTTP).

Development documents: [`docs/README.md`](docs/README.md).

## Gen 1 status

- Modular monolith: `weather`, `geo`, `routing` (+ traffic), `road`, `risk`
- REST + MCP (stdio + Streamable HTTP at `/mcp`)
- **PostGIS** models + Alembic migrations + RLS policies scaffolded
- **Redis** weather/route cache, journey state, per-tenant rate limits
- Seed: Zimbabwe places, corridor incidents, minimal OSM extract
- CI: ruff, unit/contract/BDD, tenant-isolation gate, integration job
- Gherkin acceptance automated via `pytest-bdd`

## Gen 2 status

- **RLS** with `app.tenant_id` + non-`BYPASSRLS` role `megmis_app` (`USE_APP_ROLE=true` by default when `DATABASE_APP_URL` set; compose wires both)
- Persisted API keys: create / rotate / revoke / scopes / expiry (`/api/v1/keys`)
- Webhooks: subscriptions + HMAC `X-Mamiriro-Signature` + durable delivery queue / backoff (`webhook_deliveries`)
- Journey Risk Assessment persisted via REST **and** MCP (`assess_journey_risk` resolves tenant)
- Road crowdsourcing pipeline: validation, confidence, expiry, corroboration (worker job)
- Traffic sub-module expanded under Routing (ADR-002); catalogue diagrams aligned
- Console MVP on API (`/api/v1/console`) + optional `megmis-console` compose profile (`:8088`)
- Real provider adapters: Open-Meteo / OpenWeather, Valhalla / GraphHopper / OSRM (+ HTTP unit tests; `LIVE_PROVIDERS=1` optional)
- Worker: alert fan-out, webhook drain, report validation, OSM graph-refresh markers
- `audit_log` + security event stream; Redis **token-bucket** rate limits by plan tier
- OpenAPI + CI cover Gen 2 paths; CI builds api/worker/console images

## Quick start (API only / memory fallback)

```bash
cd "/home/deuce/megmis "
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# optional for offline unit work:
# USE_PERSISTENCE=false

uvicorn megmis.main:app --reload --host 0.0.0.0 --port 8000
```

Default keys:

```text
X-API-Key: meg_local_devkey00000000000000000001   # demo
X-API-Key: meg_local_tenantb00000000000000000002  # tenant-b (isolation tests)
```

## Full Gen 1 stack (PostGIS + Redis)

```bash
docker compose up --build -d postgres redis
# wait for healthy, then:
export DATABASE_URL=postgresql+psycopg://megmis:megmis@localhost:5433/megmis
export REDIS_URL=redis://localhost:6379/0
export USE_PERSISTENCE=true
alembic upgrade head
python scripts/seed.py
uvicorn megmis.main:app --reload --port 8000
```

Postgres is published on host **5433** (avoids clashing with a local 5432).  
Or all-in-one: `docker compose up --build`.

### OSM extract

Minimal corridor graph: `data/osm/zimbabwe-harare-bulawayo.osm`  
Optional full country PBF: `./scripts/download_osm_extract.sh`

## Tests

```bash
# unit + contract + BDD + tenant isolation (no Docker)
USE_PERSISTENCE=false pytest -q -m "not integration"

# integration (PostGIS + Redis required)
INTEGRATION=1 USE_PERSISTENCE=true pytest -q -m integration

# Gen 2 platform suite (+ provider HTTP mocks)
INTEGRATION=1 USE_PERSISTENCE=true USE_APP_ROLE=true pytest -q tests/test_gen2_platform.py tests/test_providers_http.py

# Deep smokes (API must be running) — Gen1 + Gen2 connected
python scripts/gen1_deep_smoke.py
python scripts/gen2_deep_smoke.py
python scripts/gen12_deep_smoke.py
```

## Worker + optional console

```bash
docker compose up -d worker
docker compose --profile console up -d console   # http://127.0.0.1:8088/
# or locally:
python -m megmis.worker
python -m megmis.console_app
```

## Gen 3 — Voice Lab (Whisper)

```bash
pip install -e ".[voice]"          # faster-whisper + edge-tts
# SPEECH_PROVIDER=whisper WHISPER_MODEL=base
uvicorn megmis.main:app --reload --port 8000
# open Voice Lab:
#   http://127.0.0.1:8000/voice/
```

- STT: OpenAI Whisper via `faster-whisper` (falls back to mock if deps missing)
- TTS: `edge-tts` (ZA English voices; Shona/Ndebele localized reply text)
- Mutare scenario: `POST /api/v1/agents/scenarios/mutare`
- WebSocket: `ws://127.0.0.1:8000/ws/voice/{session_id}?api_key=...`

## MCP

| Transport | How |
|---|---|
| Streamable HTTP | `http://127.0.0.1:8000/mcp/` |
| stdio | `python -m megmis.mcp_stdio` |

## Publish & discovery (after MCP is green)

When build + tests are done, follow the worldwide recognition checklist:

[`docs/operations/mcp-publish-and-discover.md`](docs/operations/mcp-publish-and-discover.md)

(PyPI → deploy `/mcp` → official registry → directories → GEO docs → CI republish.)

## Layout

```text
src/megmis/     app code (api, engines, providers, mcp, db)
alembic/        migrations
scripts/        seed + entrypoint + OSM download
data/osm/       Zimbabwe corridor extract
tests/          unit, contract, bdd, isolation, integration
docs/           product & engineering specs
.github/workflows/ci.yml
```
