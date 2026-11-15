from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from megmis.common.audit import write_audit
from megmis.common.auth import (
    DEFAULT_SCOPES,
    TenantContext,
    generate_api_key,
    get_tenant,
    hash_api_key,
    invalidate_key_cache,
    require_scope,
)
from megmis.common.errors import AppError
from megmis.config import get_settings
from megmis.db.models import ApiKey
from megmis.db.session import session_scope

router = APIRouter(prefix="/keys", tags=["keys"])


class CreateKeyRequest(BaseModel):
    label: str = "default"
    scopes: list[str] = Field(default_factory=lambda: list(DEFAULT_SCOPES))
    expires_in_days: int | None = None


class KeyView(BaseModel):
    id: str
    prefix: str
    label: str
    scopes: list[str]
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    raw_key: str | None = None  # only on create/rotate


@router.get("")
async def list_keys(tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "webhook:manage")  # console/admin-ish
    with session_scope(tenant_id=str(tenant.tenant_id)) as session:
        rows = list(
            session.scalars(select(ApiKey).where(ApiKey.tenant_id == tenant.tenant_id)).all()
        )
        return {
            "data": [
                KeyView(
                    id=str(k.id),
                    prefix=k.prefix,
                    label=k.label,
                    scopes=list(k.scopes or []),
                    last_used_at=k.last_used_at,
                    expires_at=k.expires_at,
                    revoked_at=k.revoked_at,
                ).model_dump(mode="json")
                for k in rows
            ]
        }


@router.post("", status_code=201)
async def create_key(body: CreateKeyRequest, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "webhook:manage")
    settings = get_settings()
    raw = generate_api_key(settings.app_env)
    expires = None
    if body.expires_in_days:
        expires = datetime.now(UTC) + timedelta(days=body.expires_in_days)
    with session_scope(tenant_id=str(tenant.tenant_id)) as session:
        key = ApiKey(
            tenant_id=tenant.tenant_id,
            hashed_key=hash_api_key(raw),
            prefix=raw[:12],
            scopes=body.scopes or DEFAULT_SCOPES,
            label=body.label,
            expires_at=expires,
        )
        session.add(key)
        session.flush()
        write_audit(
            action="api_key_created",
            actor=tenant.api_key_prefix,
            tenant_id=tenant.tenant_id,
            resource=str(key.id),
            security=True,
        )
        return {
            "data": KeyView(
                id=str(key.id),
                prefix=key.prefix,
                label=key.label,
                scopes=list(key.scopes or []),
                expires_at=key.expires_at,
                raw_key=raw,
            ).model_dump(mode="json")
        }


@router.post("/{key_id}/rotate")
async def rotate_key(key_id: str, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "webhook:manage")
    settings = get_settings()
    raw = generate_api_key(settings.app_env)
    with session_scope(tenant_id=str(tenant.tenant_id)) as session:
        key = session.scalar(
            select(ApiKey).where(ApiKey.id == UUID(key_id), ApiKey.tenant_id == tenant.tenant_id)
        )
        if key is None or key.revoked_at is not None:
            raise AppError("NOT_FOUND", "API key not found", status_code=404)
        old_hash = key.hashed_key
        key.hashed_key = hash_api_key(raw)
        key.prefix = raw[:12]
        key.last_used_at = None
        invalidate_key_cache(old_hash)
        write_audit(
            action="api_key_rotated",
            actor=tenant.api_key_prefix,
            tenant_id=tenant.tenant_id,
            resource=key_id,
            security=True,
        )
        return {
            "data": KeyView(
                id=str(key.id),
                prefix=key.prefix,
                label=key.label,
                scopes=list(key.scopes or []),
                expires_at=key.expires_at,
                raw_key=raw,
            ).model_dump(mode="json")
        }


@router.post("/{key_id}/revoke", status_code=200)
async def revoke_key(key_id: str, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "webhook:manage")
    with session_scope(tenant_id=str(tenant.tenant_id)) as session:
        key = session.scalar(
            select(ApiKey).where(ApiKey.id == UUID(key_id), ApiKey.tenant_id == tenant.tenant_id)
        )
        if key is None:
            raise AppError("NOT_FOUND", "API key not found", status_code=404)
        key.revoked_at = datetime.now(UTC)
        invalidate_key_cache(key.hashed_key)
        write_audit(
            action="api_key_revoked",
            actor=tenant.api_key_prefix,
            tenant_id=tenant.tenant_id,
            resource=key_id,
            security=True,
        )
        return {"data": {"id": key_id, "revoked": True}}
