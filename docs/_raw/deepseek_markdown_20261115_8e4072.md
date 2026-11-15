# Observability

## Metrics
Per service/engine/provider/tenant: request_count, error_count, latency histogram,
cache_hit_ratio, provider_failover_count, rate_limit_rejections.
Routing: graph_load_time, route_p95_ms. Voice: session_count, stt_latency.

## Traces
Correlation id propagated MCP -> orchestrator -> service -> provider. One trace
per request; spans per engine call.

## Logs
JSON structured; fields: ts, level, service, tenant_id (hashed ok), request_id,
event, duration_ms. No PII.

## Dashboards
Golden signals per service; provider health; tenant usage; error budget burn.

## Alerts
Provider down > 2m; error rate > 5% 5m; p95 breach 10m; RLS policy violation
attempt logged -> page.