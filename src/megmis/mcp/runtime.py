"""Shared MCP runtime: versioning, lazy engines, auth/scopes, structured errors."""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import wraps
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from megmis import __version__
from megmis.common.auth import (
    TenantContext,
    hash_api_key,
    lookup_api_key,
    require_scope,
    seed_dev_key,
)
from megmis.common.errors import AppError
from megmis.common.schemas import LatLon, LocationInput, new_request_id
from megmis.common.tenant_ctx import get_tenant_context
from megmis.config import get_settings

# Registry / package identity (must match server.json + README mcp-name comment)
MCP_SERVER_NAME = "io.github.walter-kudzai-kamanga/megmis"
MCP_TITLE = "Mamiriro (MEGMIS)"
MCP_VERSION = __version__
MCP_SCHEMA_VERSION = "1.0.0"  # x-mcp-version for tool contracts

_READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
_WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
)


class _LazyService:
    """Construct engines on first use so provider/env changes apply after cache clears."""

    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._inst: Any | None = None

    def _get(self) -> Any:
        if self._inst is None:
            self._inst = self._factory()
        return self._inst

    def __getattr__(self, item: str) -> Any:
        return getattr(self._get(), item)

    def reset(self) -> None:
        self._inst = None


def _weather_factory():
    from megmis.engines.weather import WeatherService

    return WeatherService()


def _geo_factory():
    from megmis.engines.geo import GeoService

    return GeoService()


def _routing_factory():
    from megmis.engines.routing import RoutingService

    return RoutingService()


def _road_factory():
    from megmis.engines.road import RoadService

    return RoadService()


weather = _LazyService(_weather_factory)
geo = _LazyService(_geo_factory)
routing = _LazyService(_routing_factory)
road = _LazyService(_road_factory)


def reset_mcp_services() -> None:
    """Drop cached engines (tests / provider failover rebinding)."""
    weather.reset()
    geo.reset()
    routing.reset()
    road.reset()


def tool_error_from_app(exc: AppError, *, request_id: str | None = None) -> ToolError:
    payload = {
        "code": exc.code,
        "message": exc.message,
        "details": exc.details or {},
        "status_code": exc.status_code,
        "request_id": request_id or new_request_id(),
    }
    return ToolError(json.dumps(payload, separators=(",", ":")))


def parse_tool_error(message: str) -> dict[str, Any] | None:
    """Best-effort parse of ToolError message (may be wrapped by SDK)."""
    text = message.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, dict) and "code" in data else None
    except Exception:
        return None


def safe_tool[F: Callable[..., Any]](fn: F) -> F:
    """Map AppError / ValueError to structured ToolError JSON for clients."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except AppError as exc:
            raise tool_error_from_app(exc) from exc
        except ValueError as exc:
            raise tool_error_from_app(
                AppError("INVALID_PARAMS", str(exc), status_code=400)
            ) from exc

    return wrapper  # type: ignore[return-value]


def resolve_tenant(api_key: str | None = None) -> TenantContext | None:
    if api_key:
        looked = lookup_api_key(hash_api_key(api_key))
        if looked is None:
            raise AppError("UNAUTHORIZED", "Invalid api_key", status_code=401)
        return looked
    return get_tenant_context()


def require_tenant(
    api_key: str | None = None,
    *,
    scope: str | None = None,
    mutating: bool = False,
) -> TenantContext:
    """Resolve tenant; optionally enforce scope. Mutating tools require auth unless disabled."""
    ctx = resolve_tenant(api_key)
    settings = get_settings()
    if ctx is None:
        if settings.auth_disabled:
            ctx = seed_dev_key(settings)
        elif mutating:
            raise AppError(
                "UNAUTHORIZED",
                "Mutating MCP tools require X-API-Key (HTTP) or api_key argument",
                status_code=401,
            )
        else:
            raise AppError("UNAUTHORIZED", "Authentication required", status_code=401)
    if scope:
        require_scope(ctx, scope)
    return ctx


def loc(
    location: dict[str, Any] | None = None,
    *,
    lat: float | None = None,
    lon: float | None = None,
    name: str | None = None,
) -> LocationInput:
    if location is not None:
        if not isinstance(location, dict):
            raise AppError("INVALID_PARAMS", "location must be an object", status_code=400)
        # Reject empty objects early with a clear contract error
        if not location.get("name") and location.get("lat") is None and location.get("lon") is None:
            # also accept nested {lat,lon} only
            if "lat" not in location and "lon" not in location and "name" not in location:
                raise AppError(
                    "INVALID_LOCATION",
                    "Provide lat/lon or name",
                    status_code=400,
                )
        return LocationInput(**location)
    return LocationInput(lat=lat, lon=lon, name=name)


def require_latlon_position(position: dict[str, Any]) -> LatLon:
    if not isinstance(position, dict):
        raise AppError("INVALID_PARAMS", "current_position must be an object", status_code=400)
    if "lat" not in position or "lon" not in position:
        raise AppError("INVALID_PARAMS", "current_position requires lat and lon", status_code=400)
    lat = float(position["lat"])
    lon = float(position["lon"])
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise AppError("INVALID_PARAMS", "lat/lon out of range", status_code=400)
    return LatLon(lat=lat, lon=lon)


def require_nonempty(value: str | None, field: str) -> str:
    if value is None or not str(value).strip():
        raise AppError("INVALID_PARAMS", f"{field} is required", status_code=400)
    return str(value).strip()


def clamp_days(days: int) -> int:
    if days < 1 or days > 14:
        raise AppError("INVALID_PARAMS", "days must be 1..14", status_code=400)
    return days


def clamp_severity(severity: int) -> int:
    if severity < 1 or severity > 5:
        raise AppError("INVALID_PARAMS", "severity must be 1..5", status_code=400)
    return severity


def clamp_radius_m(radius_m: int) -> int:
    if radius_m < 1 or radius_m > 100_000:
        raise AppError("INVALID_PARAMS", "radius_m must be 1..100000", status_code=400)
    return radius_m


def dump(envelope: Any) -> dict[str, Any]:
    """Serialize an Envelope and attach MCP contract metadata (not part of REST Envelope)."""
    data = envelope.model_dump(mode="json")
    data["meta"] = {
        "x-mcp-version": MCP_SCHEMA_VERSION,
        "server": MCP_SERVER_NAME,
        "server_version": MCP_VERSION,
    }
    return data


def server_card() -> dict[str, Any]:
    """Discovery document for /.well-known and registry alignment."""
    return {
        "name": MCP_SERVER_NAME,
        "title": MCP_TITLE,
        "version": MCP_VERSION,
        "description": (
            "Mamiriro Environmental, Geospatial & Mobility Intelligence — "
            "weather, geo, safe routing, road conditions, and journey risk for Zimbabwe and beyond."
        ),
        "transports": [
            {"type": "stdio", "command": "megmis-mcp"},
            {"type": "streamable-http", "path": "/mcp/"},
        ],
        "auth": {
            "type": "api_key",
            "header": "X-API-Key",
            "mutating_tools_require_auth": True,
        },
        "schema_version": MCP_SCHEMA_VERSION,
    }
