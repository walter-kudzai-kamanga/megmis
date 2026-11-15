from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.db.models import ApiKey, UsageEvent
from megmis.db.session import get_engine, get_redis, session_scope

router = APIRouter(prefix="/console", tags=["console"])


@router.get("/health")
async def console_health(tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "webhook:manage")
    checks = {"api": "ok", "tenant": tenant.slug, "plan": tenant.plan}
    try:
        from sqlalchemy import text

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["postgres"] = f"error:{exc.__class__.__name__}"
    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error:{exc.__class__.__name__}"
    status = "ok" if all(v == "ok" or k in {"tenant", "plan"} for k, v in checks.items()) else "degraded"
    return {"status": status, "checks": checks}


@router.get("/usage")
async def console_usage(tenant: TenantContext = Depends(get_tenant), hours: int = 24):
    require_scope(tenant, "webhook:manage")
    since = datetime.now(UTC) - timedelta(hours=hours)
    with session_scope(tenant_id=str(tenant.tenant_id)) as session:
        total = session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(UsageEvent.tenant_id == tenant.tenant_id, UsageEvent.ts >= since)
        )
        by_endpoint = session.execute(
            select(UsageEvent.endpoint, func.count())
            .where(UsageEvent.tenant_id == tenant.tenant_id, UsageEvent.ts >= since)
            .group_by(UsageEvent.endpoint)
            .order_by(func.count().desc())
            .limit(20)
        ).all()
        keys = session.scalar(
            select(func.count()).select_from(ApiKey).where(ApiKey.tenant_id == tenant.tenant_id)
        )
    return {
        "data": {
            "window_hours": hours,
            "request_count": total or 0,
            "api_keys": keys or 0,
            "by_endpoint": [{"endpoint": e, "count": c} for e, c in by_endpoint],
        }
    }


@router.get("/", response_class=HTMLResponse)
async def console_home(request: Request, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "webhook:manage")
    usage = await console_usage(tenant=tenant)
    health = await console_health(tenant=tenant)
    rows = "".join(
        f"<tr><td>{r['endpoint']}</td><td>{r['count']}</td></tr>"
        for r in usage["data"]["by_endpoint"]
    ) or "<tr><td colspan=2>No usage yet</td></tr>"
    html = f"""<!doctype html>
<html><head><title>Mamiriro Console</title>
<style>
body{{font-family:ui-sans-serif,system-ui;margin:2rem;background:#0f1419;color:#e7ecf1}}
card{{display:block;padding:1rem 1.25rem;margin:1rem 0;background:#1a2332;border-radius:12px}}
table{{width:100%;border-collapse:collapse}} td,th{{padding:.5rem;border-bottom:1px solid #2a3545;text-align:left}}
.muted{{color:#9aa7b5}} h1{{margin:0 0 .25rem}}
</style></head><body>
<h1>Mamiriro Console</h1>
<p class="muted">Tenant <b>{tenant.slug}</b> · plan <b>{tenant.plan}</b></p>
<card>
  <h3>Health</h3>
  <pre>{health}</pre>
</card>
<card>
  <h3>API keys</h3>
  <p>Manage via <code>GET/POST /api/v1/keys</code>, rotate <code>POST /api/v1/keys/{{id}}/rotate</code>, revoke <code>POST /api/v1/keys/{{id}}/revoke</code>.</p>
  <p>Active keys (count): <b>{usage['data']['api_keys']}</b></p>
</card>
<card>
  <h3>Usage (last {usage['data']['window_hours']}h)</h3>
  <p>Total requests: <b>{usage['data']['request_count']}</b></p>
  <table><thead><tr><th>Endpoint</th><th>Count</th></tr></thead><tbody>{rows}</tbody></table>
</card>
</body></html>"""
    return HTMLResponse(html)
