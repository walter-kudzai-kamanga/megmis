# CI/CD Pipeline

## Stages (GitHub Actions or equivalent)
1. lint (ruff, black --check), type-check (mypy)
2. unit tests
3. contract tests (OpenAPI + MCP schemas)
4. integration tests (compose up postgis/redis/mock-providers)
5. build images (matrix: api, mcp, worker)
6. security scan (Trivy), SBOM
7. push to registry (tag: git sha + semver)
8. deploy staging; migration gate (alembic upgrade head) before app rollout
9. e2e smoke against staging
10. **Release publish** (on semver tags only): PyPI (OIDC), container registry, `mcp-publisher publish` / `server.json`, then verify official registry listing — see [mcp-publish-and-discover.md](mcp-publish-and-discover.md)

## Caching
pip/poetry cache, Docker layer cache, valhalla graph cache keyed by extract hash.

## Secrets
Injected from CI secret store; never echoed. Provider keys scoped per env.

## Gates
Tenant-isolation suite must pass. Coverage thresholds enforced. Migration check:
no pending model changes (alembic check).

## Rollback
Redeploy previous image tag; migrations are forward-only with expand/contract
pattern.