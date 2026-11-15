"""Optional megmis-console service — thin proxy/UI onto the API console MVP."""

from __future__ import annotations

import httpx
from fastapi import FastAPI, Header, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from megmis import __version__
from megmis.config import get_settings

app = FastAPI(title="Mamiriro Console", version=__version__)


def _upstream() -> str:
    return get_settings().console_upstream.rstrip("/")


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "service": "megmis-console", "upstream": _upstream()}


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/console/")


@app.api_route("/console/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
@app.api_route("/console", methods=["GET", "POST"])
async def proxy_console(
    request: Request,
    path: str = "",
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Proxy console routes to the API service, forwarding the API key."""
    suffix = path.strip("/")
    target = f"{_upstream()}/api/v1/console/" + (suffix if suffix else "")
    if request.url.query:
        target = f"{target}?{request.url.query}"
    headers = {}
    if x_api_key:
        headers["X-API-Key"] = x_api_key
    body = await request.body()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(request.method, target, content=body, headers=headers)
    ctype = resp.headers.get("content-type", "")
    if "text/html" in ctype:
        return HTMLResponse(resp.text, status_code=resp.status_code)
    if "application/json" in ctype:
        return JSONResponse(resp.json(), status_code=resp.status_code)
    return Response(content=resp.content, status_code=resp.status_code, media_type=ctype or None)


def run_console() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "megmis.console_app:app",
        host=settings.api_host,
        port=settings.console_port,
        reload=False,
    )


if __name__ == "__main__":
    run_console()
