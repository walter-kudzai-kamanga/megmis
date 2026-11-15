# Test Strategy

## Pyramid
- Unit: engines and cost model, pure functions. Fast, no IO.
- Contract: MCP tool schemas and OpenAPI validated against fixtures; provider
  adapters against recorded fixtures and sandbox contract tests.
- Integration: service + PostGIS + Redis via docker-compose, providers mocked.
- E2E: MCP client -> server -> service -> DB (compose), and REST client -> API.
- Voice: STT/TTS mocked; conversation-flow tests.

## Mandatory suites
1. Tenant isolation: every endpoint/tool exercised with two tenants; assert no
   cross-tenant leakage. CI gate.
2. Explainability: every optimize_route response includes cost_breakdown and
   explanation.
3. Confidence/expiry: stale reports lose weight; low-confidence never closes a
   road (assert closure not set).
4. Official vs model: alerts labelled; test both paths.
5. Discovery ordering: no tenant-specific tool listed before auth.
6. Provenance: every response carries data_source/confidence/retrieved_at.

## Golden fixtures
Store request/response JSON for analyze_weather_risk, optimize_route,
get_road_incidents, and the Harare->Bulawayo scenario as end-to-end test.

## Performance
p95 budgets: weather 300ms, geo 200ms, optimize_route 800ms (cached 100ms).
Load tests per endpoint with k6/locust in CI nightly.

## Coverage gates
Line >= 80% overall; engines >= 90%; MCP handlers >= 85%.