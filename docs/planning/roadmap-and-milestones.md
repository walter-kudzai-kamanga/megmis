# Roadmap & Milestones (4 generations)

## Gen 1 — Prototype
- ~10 weather tools + core routing/geospatial tools (per Section 7.1 note)
- Single tenant, MCP (stdio) + REST, mocked providers acceptable
- PostGIS + Redis via compose; CI green; tenant-isolation harness scaffolded
Exit: Harare->Bulawayo scenario returns explained route with mocked weather/road.
Ship gate (after exit): follow [mcp-publish-and-discover.md](../operations/mcp-publish-and-discover.md) so Mamiriro is installable, registry-listed, and discoverable across clients.

## Gen 2 — Multi-tenant platform ✅
- RLS tenancy (`app.tenant_id`, `megmis_app` NOBYPASSRLS, `USE_APP_ROLE` default on), API keys/scopes/rotate/revoke, webhooks (HMAC + durable `webhook_deliveries` backoff), Journey Risk Assessment (persisted REST + MCP)
- Road & Incident crowdsourcing with validation/confidence/expiry/corroboration (worker)
- Traffic sub-module in Routing (ADR-002); service-catalogue mermaid diagrams aligned
- Console MVP (API + optional `megmis-console` profile); real provider adapters + HTTP/live tests; audit_log + Redis token-bucket by plan
- CI: Gen1+Gen2 integration suite; api/worker/console image build
Exit: two tenants isolated in prod-like env; risk assessment composited. _(met — `tests/test_gen2_platform.py`, `scripts/gen12_deep_smoke.py`)_

## Gen 3 — Voice Intelligence ✅ (scaffold + Mutare path)
- Voice & Agent module; Whisper STT + edge-tts TTS; agent sessions (WebSocket + WebRTC signaling)
- Multilingual path EN → Shona / Ndebele (phrase bank + training deck)
- Voice Lab UI at `/voice/` for live mic, tool timeline, Mutare scenario, training scores
Exit: Mutare voice scenario passes E2E. _(see `tests/test_gen3_voice.py`, `/api/v1/agents/scenarios/mutare`)_

## Gen 4 — Commercial ✅ (scaffold)
- Provider failover orchestration + health-gated switch (`/api/v1/ops/providers`)
- Insurance / GovTech service packs (`/api/v1/packs`)
- Cost-weight calibration from GPS traces (`/api/v1/ops/traces`, `/ops/calibrate`)
- Object storage for audio/evidence + retention purge (local|S3; worker job)
- Observability: Prometheus `/metrics`, JSON metrics, structured JSON logs, alert hooks
- OpenAPI parity expanded (`docs/api/openapi.yaml` v0.4.0) — agents/sessions, webhooks, packs, ops
- Security: voice transcript PII redaction, secret-manager wiring (env|file|vault-stub)
- Ops docs (not built as product): runbook failover, observability, Open-Meteo licence gate
Exit: calibrated weights from ≥3 traces; packs return composite envelopes; failover health snapshot green in local. _(see `tests/test_gen4_commercial.py`)_

## Open risks / decisions
- Open-Meteo free API is **non-commercial** — set `OPEN_METEO_COMMERCIAL_OK=true` only after licence; otherwise prod blocks open-meteo primary (`checks.open_meteo_licence`).
- Google Routes / paid weather keys for production failover still optional.
- Full billing ledger / Stripe metering deferred; tenant `plan` + Redis rate tiers cover Gen 4 MVP.