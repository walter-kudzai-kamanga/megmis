# Roadmap & Milestones (4 generations)

## Gen 1 — Prototype
- ~10 weather tools + core routing/geospatial tools (per Section 7.1 note)
- Single tenant, MCP (stdio) + REST, mocked providers acceptable
- PostGIS + Redis via compose; CI green; tenant-isolation harness scaffolded
Exit: Harare->Bulawayo scenario returns explained route with mocked weather/road.

## Gen 2 — Multi-tenant platform
- RLS tenancy, API keys/scopes, webhooks, Journey Risk Assessment
- Road & Incident crowdsourcing with validation/confidence/expiry
- Traffic sub-module in Routing (ADR-002); align diagrams to service catalogue
- Console MVP (keys, usage, health)
Exit: two tenants isolated in prod-like env; risk assessment composited.

## Gen 3 — Voice Intelligence
- Voice & Agent module; STT/TTS adapters; agent sessions (WebRTC/WS)
- English first; Shona/Ndebele planned
Exit: Mutare voice scenario passes E2E.

## Gen 4 — Commercial
- Billing, plan tiers, console analytics, provider failover, insurance/govtech
  service packs, explainability tuning from real trip data
Exit: SLA met, calibrated cost weights validated.

## Open risks / decisions
- Open-M