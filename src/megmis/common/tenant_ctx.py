"""Request/MCP-scoped tenant context (contextvars)."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from megmis.common.auth import TenantContext

_tenant_ctx: ContextVar[TenantContext | None] = ContextVar("megmis_tenant", default=None)


def set_tenant_context(ctx: TenantContext | None):
    return _tenant_ctx.set(ctx)


def reset_tenant_context(token) -> None:
    _tenant_ctx.reset(token)


def get_tenant_context() -> TenantContext | None:
    return _tenant_ctx.get()
