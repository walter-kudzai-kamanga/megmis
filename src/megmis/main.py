from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from megmis import __version__
from megmis.api.v1 import api_router
from megmis.api.v1.voice_ws import router as voice_ws_router
from megmis.common.auth import seed_dev_key
from megmis.common.errors import AppError, app_error_handler
from megmis.common.observability import configure_structured_logging, metrics
from megmis.config import get_settings
from megmis.mcp.server import mcp
from megmis.providers.orchestrator import get_orchestrator

_STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.structured_logs:
        configure_structured_logging(settings.log_level)
    seed_dev_key(settings)
    # Warm Gen 4 failover orchestrator
    get_orchestrator()
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Mamiriro Intelligence API",
    description=(
        "MEGMIS REST + MCP surface — weather, geo, routing, roads, journeys, "
        "voice, commercial packs, provider failover (Gen 1–4)."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    import time

    rid = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = rid
    t0 = time.perf_counter()

    # Bind tenant for MCP (/mcp) and any path carrying X-API-Key
    from megmis.common.auth import hash_api_key, lookup_api_key
    from megmis.common.tenant_ctx import reset_tenant_context, set_tenant_context

    token = None
    api_key = request.headers.get("x-api-key")
    if api_key:
        ctx = lookup_api_key(hash_api_key(api_key))
        if ctx is not None:
            request.state.tenant = ctx
            token = set_tenant_context(ctx)

    try:
        response = await call_next(request)
    finally:
        if token is not None:
            reset_tenant_context(token)

    response.headers["X-Request-Id"] = rid
    ms = (time.perf_counter() - t0) * 1000.0
    route = request.url.path
    metrics.incr("request_count", method=request.method, path=route.split("?")[0][:80])
    metrics.observe("request_latency_ms", ms, method=request.method)
    if response.status_code >= 500:
        metrics.incr("error_count", status=str(response.status_code))

    # Usage tracking for console MVP (best-effort)
    tenant = getattr(request.state, "tenant", None)
    settings = get_settings()
    if tenant is not None and settings.use_persistence and request.url.path.startswith("/api/"):
        try:
            from megmis.db.models import UsageEvent
            from megmis.db.session import session_scope

            with session_scope(tenant_id=str(tenant.tenant_id)) as session:
                session.add(
                    UsageEvent(
                        tenant_id=tenant.tenant_id,
                        endpoint=request.url.path,
                        method=request.method,
                        status_code=response.status_code,
                        request_id=rid,
                    )
                )
        except Exception:
            pass
    return response


@app.get("/healthz", tags=["health"])
async def root_healthz() -> dict:
    settings = get_settings()
    checks: dict[str, str] = {"api": "ok"}
    if settings.use_persistence:
        try:
            from sqlalchemy import text

            from megmis.db.session import get_engine, get_redis

            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["postgres"] = "ok"
            get_redis().ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["persistence"] = f"degraded: {exc.__class__.__name__}"
    try:
        snap = get_orchestrator().health_snapshot()
        checks["providers"] = "ok" if snap.get("active") else "degraded"
    except Exception as exc:  # noqa: BLE001
        checks["providers"] = f"degraded:{exc.__class__.__name__}"
    if not settings.open_meteo_commercial_ok and settings.weather_provider == "open-meteo":
        checks["open_meteo_licence"] = "blocked_non_commercial"
    status = "ok" if all(str(v).startswith("ok") for v in checks.values()) else "degraded"
    return {
        "status": status,
        "service": "megmis",
        "version": __version__,
        "generation": 4,
        "checks": checks,
    }


@app.get("/metrics", tags=["ops"], include_in_schema=False)
async def root_metrics():
    from fastapi.responses import Response

    return Response(content=metrics.prometheus(), media_type="text/plain; version=0.0.4")


app.include_router(api_router)
app.include_router(voice_ws_router)

# Gen 3 Voice Lab UI → http://127.0.0.1:8000/voice/
if (_STATIC / "voice").is_dir():
    app.mount("/voice", StaticFiles(directory=str(_STATIC / "voice"), html=True), name="voice")


@app.get("/voice-lab", include_in_schema=False)
async def voice_lab_redirect():
    return RedirectResponse(url="/voice/")


@app.get("/.well-known/mcp.json", include_in_schema=False, tags=["mcp"])
async def mcp_well_known():
    """Server card for domain discovery (publish playbook Phase 5)."""
    from megmis.mcp.runtime import server_card

    return server_card()


@app.get("/.well-known/ai-catalog.json", include_in_schema=False, tags=["mcp"])
async def ai_catalog():
    from megmis.mcp.runtime import MCP_SERVER_NAME, MCP_VERSION, server_card

    card = server_card()
    return {
        "version": "1.0",
        "servers": [
            {
                "name": MCP_SERVER_NAME,
                "version": MCP_VERSION,
                "mcp": card,
                "endpoints": {
                    "streamable_http": "/mcp/",
                    "health": "/healthz",
                    "server_card": "/.well-known/mcp.json",
                },
            }
        ],
    }


# Mount MCP Streamable HTTP at /mcp (ADR-005)
def _mcp_transport_security():
    from mcp.server.transport_security import TransportSecuritySettings

    settings = get_settings()
    hosts = [h.strip() for h in settings.mcp_allowed_hosts.split(",") if h.strip()]
    origins = [o.strip() for o in settings.mcp_allowed_origins.split(",") if o.strip()]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


app.mount(
    "/mcp",
    mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        transport_security=_mcp_transport_security(),
    ),
)


def run_api() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "megmis.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "local",
    )


if __name__ == "__main__":
    run_api()
