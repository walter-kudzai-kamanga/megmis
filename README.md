# Mamiriro (MEGMIS)
[![Mamiriro (MEGMIS) MCP on mcprush](https://mcprush.com/badge/mamiriro-megmis-mcp/score.svg)](https://mcprush.com/to/mamiriro-megmis-mcp?ref=badge)     [![Mamiriro MCP server – quality and maintenance score on Glama](https://glama.ai/mcp/servers/walter-kudzai-kamanga/megmis/badges/score.svg)](https://glama.ai/mcp/servers/walter-kudzai-kamanga/megmis)
<!-- mcp-name: io.github.walter-kudzai-kamanga/megmis -->

**Mamiriro Environmental, Geospatial & Mobility Intelligence Server** — weather, geospatial, explained routing, road conditions, and journey-risk intelligence for Zimbabwe corridors (and beyond), exposed as **REST** and **MCP** (stdio + Streamable HTTP).

Python 3.12 · FastAPI · PostGIS · Redis · official MCP Python SDK

| Surface | Endpoint |
|---|---|
| REST API | `http://127.0.0.1:8000/api/v1/...` |
| OpenAPI / docs | `http://127.0.0.1:8000/docs` |
| MCP (HTTP) | `http://127.0.0.1:8000/mcp/` |
| MCP (stdio) | `megmis-mcp` / `python -m megmis.mcp_stdio` |
| Health | `GET /healthz` |
| Voice Lab (optional) | `http://127.0.0.1:8000/voice/` |
| Console (optional) | `http://127.0.0.1:8088/` |

**Status:** MIT-licensed **public prototype (v0.1.0)** — local mocks by default; live providers optional via env. Not a paid SLA or production weather/routing product yet. Listings must say **prototype / mock providers**.

**Naming:** **Mamiriro** is the product; **MEGMIS** is the project acronym (Environmental, Geospatial & Mobility Intelligence Server); **`megmis`** is the PyPI / CLI package.

| Public surface | URL |
|---|---|
| PyPI | https://pypi.org/project/megmis/ |
| Hosted API / MCP | https://megmis-api.onrender.com |
| MCP Streamable HTTP | https://megmis-api.onrender.com/mcp/ |
| Server card | https://megmis-api.onrender.com/.well-known/mcp.json |
| AI catalog | https://megmis-api.onrender.com/.well-known/ai-catalog.json |

Engineering docs live under [`docs/`](docs/README.md).

---

## What it does

- **Weather** — current, forecast, hourly, alerts, historical, air quality, ag conditions, activity risk
- **Geo** — geocode, reverse geocode, nearby places, emergency facilities
- **Routing** — multi-criteria `optimize_route` with cost breakdown (safest / fastest / …), reroute, corridor conditions, traffic
- **Roads** — incident reporting & crowdsourced condition pipeline
- **Risk** — journey risk assessment (REST + MCP)
- **Platform** — API keys, webhooks (HMAC), tenant RLS, rate limits, worker jobs
- **Voice (Gen 3)** — Whisper STT + edge-tts, agent sessions, WebSocket + Voice Lab
- **Commercial (Gen 4)** — provider failover, Insurance/GovTech packs, GPS cost calibration, object-store retention, `/metrics`

Providers are swappable with health-gated failover (`mock` by default; Open-Meteo / OpenWeather, Valhalla / GraphHopper / OSRM via env). **Open-Meteo free API is non-commercial** — see `OPEN_METEO_COMMERCIAL_OK`.

---

## Requirements

- Python **3.12+**
- Docker (recommended for PostGIS + Redis)
- Optional: `[voice]` extras for Whisper / TTS

---

## Install (PyPI / local package)

Once published (or from a built wheel):

```bash
pip install megmis
# optional voice extras: pip install "megmis[voice]"

# stdio MCP for Cursor / Claude / VS Code / Windsurf
USE_PERSISTENCE=false megmis-mcp

# or one-shot without a permanent install:
uvx --from megmis megmis-mcp
```

Build locally without uploading:

```bash
pip install -e ".[dev]"
python -m build
twine check dist/*
```

Release to PyPI: push a `v*` tag after configuring Trusted Publishing (see [`.github/workflows/release.yml`](.github/workflows/release.yml)).

---

## Quick start

### 1. API only (in-memory / no Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# USE_PERSISTENCE=false   # optional for offline unit work

uvicorn megmis.main:app --reload --host 0.0.0.0 --port 8000
# or: megmis-api
```

### 2. Full stack (PostGIS + Redis)

Postgres is published on host **5433** (avoids clashing with a local 5432).

```bash
docker compose up --build -d postgres redis
cp .env.example .env

export DATABASE_URL=postgresql+psycopg://megmis:megmis@localhost:5433/megmis
export REDIS_URL=redis://localhost:6379/0
export USE_PERSISTENCE=true

alembic upgrade head
python scripts/seed.py
uvicorn megmis.main:app --reload --port 8000
```

All-in-one (API + DB + Redis + worker wiring):

```bash
docker compose up --build
```

### Dev API keys

```text
X-API-Key: meg_local_devkey00000000000000000001   # demo tenant
X-API-Key: meg_local_tenantb00000000000000000002  # tenant-b (isolation tests)
```

### Auth

- REST and MCP HTTP: send `X-API-Key: meg_…` on every request (hashed at rest; scopes enforced).
- MCP stdio: seeds the demo tenant from `DEV_API_KEY` / settings (no header needed locally).
- Mutating MCP tools also accept an `api_key` argument when no HTTP context is present.
- OAuth / OIDC for remote connectors is planned for commercial hosting — not required for local stdio.
- Details: [`docs/engineering/security-and-tenancy.md`](docs/engineering/security-and-tenancy.md).

---

## REST examples

```bash
export DEV_API_KEY=meg_local_devkey00000000000000000001

curl -s -H "X-API-Key: $DEV_API_KEY" \
  "http://127.0.0.1:8000/api/v1/weather/current?name=Harare" | jq

curl -s -H "X-API-Key: $DEV_API_KEY" -H "Content-Type: application/json" \
  -d '{"origin":{"name":"Harare"},"destination":{"name":"Bulawayo"},"profile":"safest"}' \
  http://127.0.0.1:8000/api/v1/routes/optimize | jq

# Gen 4 commercial pack + provider health
curl -s -H "X-API-Key: $DEV_API_KEY" http://127.0.0.1:8000/api/v1/packs | jq
curl -s -H "X-API-Key: $DEV_API_KEY" http://127.0.0.1:8000/api/v1/ops/providers | jq
curl -s http://127.0.0.1:8000/metrics | head
```

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).  
Contract: [`docs/api/openapi.yaml`](docs/api/openapi.yaml) (v0.4.0). Gen 4 ops notes: [`docs/operations/gen4-commercial.md`](docs/operations/gen4-commercial.md).

---

## MCP

Same tools as REST (weather, geo, routing, roads, journey risk, traffic), plus `create_journey`. Contracts: [`docs/api/mcp-tool-contracts.md`](docs/api/mcp-tool-contracts.md).

Mutating tools (`report_road_condition`, `create_journey`, `reroute`) require `X-API-Key` on HTTP `/mcp`, or an `api_key` argument. Stdio seeds the demo tenant automatically.

| Transport | How |
|---|---|
| Streamable HTTP | `http://127.0.0.1:8000/mcp/` (same process as the API) |
| stdio | `megmis-mcp` or `python -m megmis.mcp_stdio` |

### Cursor / Claude Desktop (stdio)

After `pip install -e .` (or a published `megmis` wheel), point the client at the console script or module:

```json
{
  "mcpServers": {
    "mamiriro": {
      "command": "megmis-mcp",
      "env": {
        "USE_PERSISTENCE": "false",
        "DEV_API_KEY": "meg_local_devkey00000000000000000001"
      }
    }
  }
}
```

Editable checkout (absolute venv path):

```json
{
  "mcpServers": {
    "mamiriro": {
      "command": "/ABS/PATH/TO/.venv/bin/python",
      "args": ["-m", "megmis.mcp_stdio"],
      "cwd": "/ABS/PATH/TO/megmis"
    }
  }
}
```

### VS Code (MCP extension / `mcp.json`)

```json
{
  "servers": {
    "mamiriro": {
      "type": "stdio",
      "command": "megmis-mcp",
      "env": {
        "USE_PERSISTENCE": "false",
        "DEV_API_KEY": "meg_local_devkey00000000000000000001"
      }
    }
  }
}
```

### Windsurf

Same stdio shape as Cursor — add under MCP servers:

```json
{
  "mcpServers": {
    "mamiriro": {
      "command": "megmis-mcp",
      "env": {
        "USE_PERSISTENCE": "false",
        "DEV_API_KEY": "meg_local_devkey00000000000000000001"
      }
    }
  }
}
```

### Claude Code

Stdio (after `pip install megmis` or `uvx`):

```bash
claude mcp add mamiriro --env USE_PERSISTENCE=false -- megmis-mcp
```

Or remote HTTP (when the CLI supports URL transports):

```text
https://megmis-api.onrender.com/mcp/
```

### Remote / HTTP clients

Local API (`uvicorn` or Docker):

```text
http://127.0.0.1:8000/mcp/
```

**Hosted prototype (Render):**

```text
https://megmis-api.onrender.com/mcp/
```

Pass `X-API-Key` the way your client supports custom headers (or use tool `api_key` on mutating calls). Cursor-style remote entry:

```json
{
  "mcpServers": {
    "mamiriro-http": {
      "url": "https://megmis-api.onrender.com/mcp/",
      "headers": {
        "X-API-Key": "YOUR_RENDER_DEV_API_KEY"
      }
    }
  }
}
```

Local override while developing:

```json
{
  "mcpServers": {
    "mamiriro-http-local": {
      "url": "http://127.0.0.1:8000/mcp/",
      "headers": {
        "X-API-Key": "meg_local_devkey00000000000000000001"
      }
    }
  }
}
```

### ChatGPT (Connectors / custom MCP)

1. Use a ChatGPT plan that supports custom MCP / connectors.
2. Add a connector pointing at Streamable HTTP: `https://megmis-api.onrender.com/mcp/`
3. Send auth as `X-API-Key: <key>` if the UI exposes custom headers (mutating tools require it).
4. Label the connector **prototype / mock providers** until live adapters are the default.

Discovery without a directory: open `https://megmis-api.onrender.com/.well-known/mcp.json`.

### Example prompts

- Plan the safest Harare → Bulawayo drive and explain the cost breakdown.
- Assess weather risk for outdoor work in Mutare tomorrow.
- List road incidents on the Harare–Bulawayo corridor.
- Assess journey risk from Harare to Bulawayo for a light truck.

---

## Configuration

Copy [`.env.example`](.env.example) → `.env`. Important knobs:

| Variable | Purpose |
|---|---|
| `USE_PERSISTENCE` | `true` → PostGIS + Redis; `false` → memory fallback |
| `DATABASE_URL` / `DATABASE_APP_URL` | Owner vs RLS app role (`megmis_app`) |
| `USE_APP_ROLE` | Enforce tenant RLS via app role |
| `WEATHER_PROVIDER` | `mock` \| `open-meteo` \| `openweather` |
| `ROUTING_PROVIDER` | `mock` \| `valhalla` \| `graphhopper` \| `osrm` |
| `GEOCODE_PROVIDER` | `mock` \| `nominatim` |
| `SPEECH_PROVIDER` / `TTS_PROVIDER` | `whisper` / `edge` (voice extras) |
| `OSM_EXTRACT_PATH` | Corridor graph for local Dijkstra |

OSM seed extract: `data/osm/zimbabwe-harare-bulawayo.osm`  
Optional full country PBF: `./scripts/download_osm_extract.sh`

---

## Worker & console

```bash
docker compose up -d worker
docker compose --profile console up -d console   # http://127.0.0.1:8088/

# or locally
megmis-worker          # or: python -m megmis.worker
python -m megmis.console_app
```

Worker drains webhooks, validates road reports, fan-outs alerts, and marks OSM graph refresh.

---

## Voice Lab (optional)

```bash
pip install -e ".[voice]"
# SPEECH_PROVIDER=whisper  WHISPER_MODEL=base  TTS_PROVIDER=edge
uvicorn megmis.main:app --reload --port 8000
# open http://127.0.0.1:8000/voice/
```

- STT: OpenAI Whisper via `faster-whisper` (falls back to mock if deps missing)
- TTS: `edge-tts` (ZA English; Shona/Ndebele localized reply text)
- Scenario: `POST /api/v1/agents/scenarios/mutare`
- WebSocket: `ws://127.0.0.1:8000/ws/voice/{session_id}?api_key=...`

---

## Tests

```bash
# unit + contract + BDD + tenant isolation (no Docker)
USE_PERSISTENCE=false pytest -q -m "not integration"

# integration (PostGIS + Redis required)
INTEGRATION=1 USE_PERSISTENCE=true pytest -q -m integration

# Gen 2 platform + provider HTTP mocks
INTEGRATION=1 USE_PERSISTENCE=true USE_APP_ROLE=true \
  pytest -q tests/test_gen2_platform.py tests/test_providers_http.py

# deep smokes (API must be running)
python scripts/gen1_deep_smoke.py
python scripts/gen2_deep_smoke.py
python scripts/gen12_deep_smoke.py
```

CI: [`.github/workflows/ci.yml`](.github/workflows/ci.yml). Strategy: [`docs/quality/test-strategy.md`](docs/quality/test-strategy.md).

---

## Publish & discovery

Playbook: [`docs/operations/mcp-publish-and-discover.md`](docs/operations/mcp-publish-and-discover.md)

| Phase | Status |
|---|---|
| 0 Pre-flight | Done |
| 2 PyPI package + Trusted Publishing workflow | Done (upload on first `v*` tag after PyPI pending publisher) |
| 3 Deploy HTTPS `/mcp` | **Live:** https://megmis-api.onrender.com (`/mcp/`) |
| 4 Official MCP Registry (`server.json`) | Manifest ready; publish after PyPI |
| 6+ Directories / GEO | After registry |

### Hosted MCP (Phase 3)

```bash
# fastest: Render Blueprint (render.yaml) or: fly deploy
# then:
./scripts/verify_remote_mcp.sh https://YOURHOST
```

Set `PUBLIC_BASE_URL=https://YOURHOST` so MCP Host allowlisting and `/.well-known/mcp.json` include the public URL.

```bash
# after PyPI Trusted Publisher is linked:
git tag v0.1.0
git push origin v0.1.0
```

---

## Project layout

```text
src/megmis/
  main.py           FastAPI app + /mcp mount + voice static
  mcp_stdio.py      stdio MCP entry (megmis-mcp)
  worker.py         background jobs (megmis-worker)
  console_app.py    optional ops console
  api/v1/           REST routers
  mcp/              MCP tools, resources, prompts
  engines/          weather, geo, routing, road, risk, …
  providers/        Protocol adapters (mock + live)
  db/               SQLAlchemy models, Redis, repos
  common/           auth, schemas, errors
alembic/            migrations (+ RLS)
scripts/            seed, entrypoint, smokes, OSM download
data/osm/           Zimbabwe corridor extract
tests/              unit, contract, BDD, isolation, integration
docs/               ADRs, OpenAPI, MCP contracts, ops
```

---

## Documentation map

| Doc | Contents |
|---|---|
| [`docs/README.md`](docs/README.md) | Full document index |
| [`docs/architecture/adr-0001-architecture-decisions.md`](docs/architecture/adr-0001-architecture-decisions.md) | ADRs |
| [`docs/architecture/service-catalogue.md`](docs/architecture/service-catalogue.md) | Service ownership |
| [`docs/api/openapi.yaml`](docs/api/openapi.yaml) | REST contract |
| [`docs/api/mcp-tool-contracts.md`](docs/api/mcp-tool-contracts.md) | MCP tools / resources / prompts |
| [`docs/planning/roadmap-and-milestones.md`](docs/planning/roadmap-and-milestones.md) | Gen 1–4 roadmap |
| [`docs/operations/docker-and-compose.md`](docs/operations/docker-and-compose.md) | Compose & env |
| [`docs/operations/mcp-publish-and-discover.md`](docs/operations/mcp-publish-and-discover.md) | Publish & discovery gate |

---

## License

[MIT](LICENSE) — free to use, modify, and redistribute. Provided as-is; no warranty.
