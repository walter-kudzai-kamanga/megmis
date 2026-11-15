# Mamiriro (MEGMIS) — Development Documents

Structured engineering docs for the **Mamiriro Environmental, Geospatial & Mobility Intelligence Server** (MEGMIS): a multi-tenant MCP + REST intelligence platform for weather, geospatial, routing, road conditions, journey risk, and voice agents.

**Gen 1 implementation is in the repo root** (`src/megmis/`, Alembic, compose, CI). Start here for product context: [Technical Specification](overview/technical-specification.docx), then [Service Catalogue](architecture/service-catalogue.md) and [ADRs](architecture/adr-0001-architecture-decisions.md).

---

## Document map

| Section | Purpose |
|---|---|
| [overview/](overview/) | Product vision, full technical specification, early ideation |
| [architecture/](architecture/) | ADRs and canonical service catalogue |
| [domain/](domain/) | Domain entities, PostGIS schema, migrations |
| [api/](api/) | OpenAPI surface and MCP tool/resource/prompt contracts |
| [engineering/](engineering/) | Route cost model, providers, security & tenancy |
| [operations/](operations/) | Docker, CI/CD, observability, Gen 4 commercial runbook, MCP publish & discovery |
| [quality/](quality/) | Test strategy and Gherkin acceptance scenarios |
| [planning/](planning/) | Generational roadmap and open decisions |
| [_raw/](_raw/) | Original DeepSeek export filenames (archived) |

---

## Overview

| Document | Description |
|---|---|
| [technical-specification.docx](overview/technical-specification.docx) | Draft v0.1 full product/tech spec (15 Nov 2026) |
| [source-ideas-weather-mcp.pdf](overview/source-ideas-weather-mcp.pdf) | Early ChatGPT ideation that grew into MEGMIS |

## Architecture

| Document | Description |
|---|---|
| [adr-0001-architecture-decisions.md](architecture/adr-0001-architecture-decisions.md) | ADR-001…009 (monolith, tenancy RLS, MCP SDK, providers, voice isolation) |
| [service-catalogue.md](architecture/service-catalogue.md) | Canonical services, ownership map, dependency graph |

## Domain

| Document | Description |
|---|---|
| [domain-model.md](domain/domain-model.md) | Entities (Tenant, Route, Journey, RoadReport, …), conventions, error model |
| [data-model-and-migrations.md](domain/data-model-and-migrations.md) | PostGIS tables, indexes, RLS, Redis keys, S3 layout, retention |

## API & MCP

| Document | Description |
|---|---|
| [openapi.yaml](api/openapi.yaml) | OpenAPI 3.1 REST surface (weather, geo, routes, roads, agents, webhooks) |
| [mcp-tool-contracts.md](api/mcp-tool-contracts.md) | MCP tools, resources, prompts, discovery/auth ordering |

## Engineering

| Document | Description |
|---|---|
| [route-cost-model.md](engineering/route-cost-model.md) | Dynamic cost function, profiles, penalties, explainability |
| [provider-adapter-contract.md](engineering/provider-adapter-contract.md) | Weather/Routing/Geocoding/Speech Protocol adapters |
| [security-and-tenancy.md](engineering/security-and-tenancy.md) | API keys, RLS, rate limits, audit, webhooks, PII |

## Operations

| Document | Description |
|---|---|
| [docker-and-compose.md](operations/docker-and-compose.md) | Images, compose topology, env vars, healthchecks |
| [cicd-pipeline.md](operations/cicd-pipeline.md) | Lint → test → build → scan → deploy stages and gates |
| [observability.md](operations/observability.md) | Metrics, traces, logs, dashboards, alerts |
| [operations-runbook.md](operations/operations-runbook.md) | Backups, failover, incidents, capacity, on-call |
| [gen4-commercial.md](operations/gen4-commercial.md) | Packs, GPS calibration, object retention, Open-Meteo licence gate |
| [mcp-publish-and-discover.md](operations/mcp-publish-and-discover.md) | **Final gate:** PyPI, deploy, official registry, directories, GEO, CI republish |

## Quality

| Document | Description |
|---|---|
| [test-strategy.md](quality/test-strategy.md) | Pyramid, mandatory suites, golden fixtures, coverage gates |
| [acceptance-scenarios.feature](quality/acceptance-scenarios.feature) | Gherkin: weather risk, Harare→Bulawayo routing, Mutare voice, tenant isolation |

## Planning

| Document | Description |
|---|---|
| [roadmap-and-milestones.md](planning/roadmap-and-milestones.md) | Gen 1–4 (prototype → multi-tenant → voice → commercial) |

---

## Suggested reading order (build Gen 1)

1. Overview technical specification  
2. Architecture ADRs + service catalogue  
3. MCP tool contracts + OpenAPI  
4. Domain model + data model  
5. Provider adapters + route cost model  
6. Security & tenancy  
7. Docker/compose + test strategy + acceptance scenarios  
8. CI/CD, observability, runbook  
9. **After MCP + tests are green:** [MCP publish & discover](operations/mcp-publish-and-discover.md)  
10. Roadmap for Gen 2+ scope  

---

## Notes

- Canonical service list is [service-catalogue.md](architecture/service-catalogue.md); diagrams in the DOCX should stay aligned with it (ADR-002).
- Original DeepSeek export files are preserved under [`_raw/`](_raw/) for provenance.
- `roadmap-and-milestones.md` ends mid-bullet under “Open risks / decisions” (export appears truncated).
