# Security & Tenancy

## API keys
Format: meg_<env>_<random32>. Store SHA-256 hash + prefix only. Rotate via
POST /api/v1/keys/{id}/rotate. Scopes: weather:read, geo:read, routing:read,
road:write, road:read, journey:write, agent:use, webhook:manage.

## Tenant isolation
RLS per ADR-004. Every request sets app.tenant_id before queries. Integration
tests run all endpoints as tenant A against tenant B data and assert 404/empty.

## Rate limiting
Per-tenant token bucket in Redis. Tiers: free, pro, enterprise. 429 with
Retry-After. Per-endpoint caps too.

## Audit
Record at: authentication, authorization, tenant context set, tool handler entry,
shared-service call. Fields in audit_log table. Security-sensitive events
(auth failures, scope denials, key changes) also to structured log stream.

## Webhooks
HMAC-SHA256 signature header X-Mamiriro-Signature over raw body + timestamp;
replay window 5m; per-subscription secret.

## PII
Voice transcripts pseudonymised; reporter_ref is a rotating pseudonym. No PII in
logs. Audio retention configurable per tenant.

## Secrets
Provider keys injected via env/secret manager, never in images. Per-environment
isolation.