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

## Gen 4 — Commercial
- Billing, plan tiers, console analytics, provider failover, insurance/govtech
  service packs, explainability tuning from real trip data
Exit: SLA met, calibrated cost weights validated.

## Open risks / decisions
- Open-M