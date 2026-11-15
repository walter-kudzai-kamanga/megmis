# Gen 4 — Commercial ops notes

Cross-cutting ops for the commercial generation. Product surfaces are REST/MCP;
this page is runbook detail only.

## Service packs

| Pack id | Vertical | Needs |
|---|---|---|
| `insurance.corridor` | Insurance | origin + destination |
| `govtech.emergency` | GovTech | location (or origin) |
| `govtech.mobility` | GovTech | origin + destination |

```bash
curl -s -H "X-API-Key: $DEV_API_KEY" http://127.0.0.1:8000/api/v1/packs | jq
curl -s -H "X-API-Key: $DEV_API_KEY" -H "Content-Type: application/json" \
  -d '{"origin":{"name":"Harare"},"destination":{"name":"Mutare"}}' \
  http://127.0.0.1:8000/api/v1/packs/insurance.corridor/run | jq
```

MCP: `list_service_packs`, `run_service_pack`.

## GPS cost-weight calibration

1. Ingest ≥3 trip traces (`POST /api/v1/ops/traces`) with `points[{lat,lon,speed_mps}]`.
2. `POST /api/v1/ops/calibrate` with `{profile, min_traces}`.
3. Inspect `GET /api/v1/ops/weights`.

## Observability

- Prometheus: `GET /metrics` and `GET /api/v1/metrics`
- JSON snapshot: `GET /api/v1/ops/metrics`
- Structured JSON logs when `STRUCTURED_LOGS=true`
- Alerts: in-process hooks on provider down / failover (wire to pager in staging)

## Security beyond API key

- Voice transcripts redacted (`megmis.common.pii`) before session persist
- Secrets: `SECRET_MANAGER=env|file|vault-stub` (OpenWeather key via manager)
- Object artefacts tenant-scoped + RLS when persistence is on

## Open risk

Do **not** enable live Open-Meteo in commercial prod until a paid/commercial
licence is in place (`OPEN_METEO_COMMERCIAL_OK=true`). Prefer OpenWeather or mock
until then.
