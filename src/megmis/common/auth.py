from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, Header, Request
from sqlalchemy import select

from megmis.common.audit import write_audit
from megmis.common.errors import AppError
from megmis.config import Settings, get_settings
from megmis.db.models import ApiKey, Tenant
from megmis.db.redis_cache import token_bucket_allow
from megmis.db.session import session_scope

DEFAULT_SCOPES = [
    "weather:read",
    "geo:read",
    "routing:read",
    "road:read",
    "road:write",
    "journey:write",
    "agent:use",
    "webhook:manage",
]


@dataclass
class TenantContext:
    tenant_id: UUID
    slug: str
    plan: str = "free"
    scopes: list[str] = field(default_factory=list)
    api_key_prefix: str = ""
    api_key_id: UUID | None = None


_KEY_STORE: dict[str, TenantContext] = {}
_FALLBACK_TENANT_ID = uuid4()


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_api_key(env: str = "local") -> str:
    return f"meg_{env}_{secrets.token_hex(16)}"


def _ctx_from_row(key: ApiKey, tenant: Tenant) -> TenantContext:
    return TenantContext(
        tenant_id=tenant.id,
        slug=tenant.slug,
        plan=tenant.plan or "free",
        scopes=list(key.scopes or DEFAULT_SCOPES),
        api_key_prefix=key.prefix,
        api_key_id=key.id,
    )


def seed_dev_key(settings: Settings) -> TenantContext:
    raw = settings.dev_api_key
    digest = hash_api_key(raw)
    prefix = raw[:12]

    try:
        with session_scope(admin=True) as session:
            tenant = session.scalar(select(Tenant).where(Tenant.slug == settings.default_tenant_slug))
            if tenant is None:
                tenant = Tenant(
                    name="Demo Tenant",
                    slug=settings.default_tenant_slug,
                    plan="pro",
                    status="active",
                    settings={},
                )
                session.add(tenant)
                session.flush()

            key = session.scalar(select(ApiKey).where(ApiKey.hashed_key == digest))
            if key is None:
                key = ApiKey(
                    tenant_id=tenant.id,
                    hashed_key=digest,
                    prefix=prefix,
                    scopes=DEFAULT_SCOPES,
                    label="dev",
                )
                session.add(key)
                session.flush()

            other = session.scalar(select(Tenant).where(Tenant.slug == "tenant-b"))
            if other is None:
                other = Tenant(name="Tenant B", slug="tenant-b", plan="free", status="active")
                session.add(other)
                session.flush()
                other_raw = settings.dev_api_key_b
                other_key = ApiKey(
                    tenant_id=other.id,
                    hashed_key=hash_api_key(other_raw),
                    prefix=other_raw[:12],
                    scopes=DEFAULT_SCOPES,
                    label="tenant-b",
                )
                session.add(other_key)
                _KEY_STORE[hash_api_key(other_raw)] = _ctx_from_row(other_key, other)
            else:
                other_raw = settings.dev_api_key_b
                other_key = session.scalar(
                    select(ApiKey).where(ApiKey.hashed_key == hash_api_key(other_raw))
                )
                if other_key:
                    _KEY_STORE[hash_api_key(other_raw)] = _ctx_from_row(other_key, other)

            ctx = _ctx_from_row(key, tenant)
            _KEY_STORE[digest] = ctx
            return ctx
    except Exception:
        ctx = TenantContext(
            tenant_id=_FALLBACK_TENANT_ID,
            slug=settings.default_tenant_slug,
            plan="pro",
            scopes=DEFAULT_SCOPES,
            api_key_prefix=prefix,
        )
        _KEY_STORE[digest] = ctx
        other_raw = settings.dev_api_key_b
        _KEY_STORE[hash_api_key(other_raw)] = TenantContext(
            tenant_id=uuid4(),
            slug="tenant-b",
            plan="free",
            scopes=DEFAULT_SCOPES,
            api_key_prefix=other_raw[:12],
        )
        return ctx


def lookup_api_key(digest: str) -> TenantContext | None:
    """Resolve API key hash → tenant (uses owner/admin engine; RLS chicken-and-egg)."""
    if digest in _KEY_STORE:
        cached = _KEY_STORE[digest]
        # Still re-validate expiry/revoke from DB when persistence is on
        _ = cached
    try:
        with session_scope(admin=True) as session:
            key = session.scalar(select(ApiKey).where(ApiKey.hashed_key == digest))
            if key is None:
                return None
            if key.revoked_at is not None:
                return None
            if key.expires_at is not None and key.expires_at < datetime.now(UTC):
                return None
            tenant = session.get(Tenant, key.tenant_id)
            if tenant is None or tenant.status != "active":
                return None
            key.last_used_at = datetime.now(UTC)
            ctx = _ctx_from_row(key, tenant)
            _KEY_STORE[digest] = ctx
            return ctx
    except Exception:
        return _KEY_STORE.get(digest)


def invalidate_key_cache(digest: str | None = None) -> None:
    if digest:
        _KEY_STORE.pop(digest, None)
    else:
        _KEY_STORE.clear()


def require_scope(ctx: TenantContext, scope: str) -> None:
    if scope not in ctx.scopes and "*" not in ctx.scopes:
        write_audit(
            action="scope_denied",
            actor=ctx.api_key_prefix or "unknown",
            tenant_id=ctx.tenant_id,
            resource=scope,
            security=True,
        )
        raise AppError("FORBIDDEN", f"Missing scope: {scope}", status_code=403)


async def get_tenant(
    request: Request,
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> TenantContext:
    if settings.auth_disabled:
        ctx = TenantContext(
            tenant_id=_FALLBACK_TENANT_ID,
            slug=settings.default_tenant_slug,
            plan="enterprise",
            scopes=["*"],
        )
        request.state.tenant = ctx
        return ctx

    if not x_api_key:
        write_audit(action="auth_missing_key", security=True, ip=request.client.host if request.client else None)
        raise AppError("UNAUTHORIZED", "Missing X-API-Key header", status_code=401)

    ctx = lookup_api_key(hash_api_key(x_api_key))
    if ctx is None:
        write_audit(
            action="auth_failure",
            actor=x_api_key[:12],
            security=True,
            ip=request.client.host if request.client else None,
        )
        raise AppError("UNAUTHORIZED", "Invalid API key", status_code=401)

    if settings.use_persistence:
        allowed, retry_after = token_bucket_allow(
            str(ctx.tenant_id),
            plan=ctx.plan,
            endpoint=request.url.path,
        )
        if not allowed:
            raise AppError(
                "RATE_LIMITED",
                "Too many requests",
                status_code=429,
                details={"Retry-After": str(retry_after)},
            )

    write_audit(
        action="tenant_context_set",
        actor=ctx.api_key_prefix,
        tenant_id=ctx.tenant_id,
        resource=request.url.path,
        request_id=getattr(request.state, "request_id", None),
    )
    request.state.tenant = ctx
    return ctx
