# ADR-0001 — Architecture Decisions (Index)

Status: Proposed
Date: 2026-11-15
Deciders: Platform lead, Backend lead, MCP lead

## ADR-001: Modular monolith for Phase 1
Decision: Build Mamiriro as a modular monolith (single deployable) with strict
internal module boundaries (weather, geo, routing, road, risk, voice).
Rationale: fastest path to prototype; engines remain interface-separated so they
can be extracted into services later without changing contracts.
Consequences: one CI/CD pipeline; module boundary tests required; extraction path
documented in ADR-001a.

## ADR-002: Traffic Intelligence placement
Decision: Traffic Intelligence is a *sub-module of Routing & Optimization* for
Phase 1, exposed internally as `traffic` module with its own interface.
Rationale: resolves the spec's open question (Section 4.5 alignment note); avoids
a premature service split while keeping an extraction seam.
Consequences: Figure 1, Section 4.2 and Figure 2 must be updated to show traffic
as part of Routing & Optimization. Revisit before Phase 2.

## ADR-003: Provider abstraction
Decision: Every external provider (weather, routing, geocoding, speech) sits
behind a Python Protocol/ABC adapter. No engine imports a provider SDK directly.
Rationale: Section 4.3 provider abstraction layer; Section 1 provider independence.
Consequences: adapter contract tests required; one adapter per provider; runtime
provider selection via config.

## ADR-004: Tenancy model
Decision: Single database, single schema, PostgreSQL Row-Level Security (RLS) with
a `tenant_id` column on every tenant-scoped table.
Rationale: Section 2.1 strict tenant isolation with operational simplicity.
Consequences: every query runs under a tenant context; RLS policies tested in CI;
superuser bypass disabled for app role.

## ADR-005: MCP transport and SDK
Decision: Python MCP SDK; support stdio transport for local/dev and HTTP+SSE for
hosted deployment. MCP server is a thin adapter over shared application services.
Rationale: Section 7.6 architectural distinction (handlers stay thin).
Consequences: tool handlers only validate/authorise/delegate/format.

## ADR-006: Language/runtime
Decision: Python 3.12, FastAPI for REST, MCP Python SDK, SQLAlchemy 2 + Alembic,
Pydantic v2 for schemas, pytest for tests.
Rationale: ecosystem fit for MCP and geospatial/AI work.

## ADR-007: Geospatial storage
Decision: PostgreSQL + PostGIS only for Phase 1; no separate geospatial service.
Consequences: GiST indexes; spatial queries confined to geo module.

## ADR-008: Auth
Decision: API keys (hashed, scoped) for v1; OAuth2/OIDC deferred to Phase 2.
Consequences: key rotation and scope model defined in security spec.

## ADR-009: Voice Intelligence isolation
Decision: Voice & Agent Intelligence is an independent module consuming multiple
MCP servers; not embedded in Weather or Routing.
Rationale: Section 4.4 architectural rules.