from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.common.errors import AppError
from megmis.config import get_settings
from megmis.db.models import WebhookDelivery, WebhookSubscription
from megmis.db.session import session_scope

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Exponential backoff bases (seconds) by attempt index
_BACKOFF = (5, 15, 60, 300, 900, 1800, 3600, 7200)


class CreateWebhook(BaseModel):
    url: HttpUrl
    events: list[str] = Field(default_factory=lambda: ["road.report", "journey.risk", "alert.weather"])


def sign_payload(secret: str, body: bytes, timestamp: int) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    return mac.hexdigest()


def verify_signature(secret: str, body: bytes, signature: str, timestamp: int, window_s: int = 300) -> bool:
    if abs(int(time.time()) - timestamp) > window_s:
        return False
    expected = sign_payload(secret, body, timestamp)
    return hmac.compare_digest(expected, signature)


@router.post("", status_code=201)
async def register_webhook(body: CreateWebhook, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "webhook:manage")
    secret = secrets.token_hex(24)
    with session_scope(tenant_id=str(tenant.tenant_id)) as session:
        sub = WebhookSubscription(
            tenant_id=tenant.tenant_id,
            url=str(body.url),
            secret=secret,
            events=body.events,
            active=True,
        )
        session.add(sub)
        session.flush()
        return {
            "data": {
                "id": str(sub.id),
                "url": sub.url,
                "events": sub.events,
                "secret": secret,  # shown once
                "active": True,
            }
        }


@router.get("")
async def list_webhooks(tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "webhook:manage")
    with session_scope(tenant_id=str(tenant.tenant_id)) as session:
        rows = list(
            session.scalars(
                select(WebhookSubscription).where(
                    WebhookSubscription.tenant_id == tenant.tenant_id
                )
            ).all()
        )
        return {
            "data": [
                {
                    "id": str(r.id),
                    "url": r.url,
                    "events": r.events,
                    "active": r.active,
                    "failure_count": r.failure_count,
                    "last_delivery_at": r.last_delivery_at.isoformat() if r.last_delivery_at else None,
                }
                for r in rows
            ]
        }


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "webhook:manage")
    with session_scope(tenant_id=str(tenant.tenant_id)) as session:
        row = session.scalar(
            select(WebhookSubscription).where(
                WebhookSubscription.id == UUID(webhook_id),
                WebhookSubscription.tenant_id == tenant.tenant_id,
            )
        )
        if row is None:
            raise AppError("NOT_FOUND", "Webhook not found", status_code=404)
        session.delete(row)
        return {"data": {"deleted": True}}


def enqueue_event(tenant_id: str, event: str, payload: dict) -> list[str]:
    """Persist durable delivery rows for matching subscriptions (worker drains)."""
    ids: list[str] = []
    now = datetime.now(UTC)
    with session_scope(tenant_id=tenant_id) as session:
        subs = list(
            session.scalars(
                select(WebhookSubscription).where(
                    WebhookSubscription.tenant_id == UUID(tenant_id),
                    WebhookSubscription.active.is_(True),
                )
            ).all()
        )
        for sub in subs:
            if sub.events and event not in sub.events and "*" not in sub.events:
                continue
            row = WebhookDelivery(
                id=uuid4(),
                tenant_id=UUID(tenant_id),
                subscription_id=sub.id,
                event=event,
                payload=payload,
                status="pending",
                attempts=0,
                next_attempt_at=now,
            )
            session.add(row)
            session.flush()
            ids.append(str(row.id))
    return ids


def _attempt_http(sub: WebhookSubscription, event: str, payload: dict) -> tuple[bool, str | None, int | None]:
    body = json.dumps({"event": event, "payload": payload}).encode()
    ts = int(time.time())
    sig = sign_payload(sub.secret, body, ts)
    headers = {
        "Content-Type": "application/json",
        "X-Mamiriro-Signature": sig,
        "X-Mamiriro-Timestamp": str(ts),
    }
    try:
        resp = httpx.post(sub.url, content=body, headers=headers, timeout=5.0)
        ok = 200 <= resp.status_code < 300
        return ok, None if ok else f"http_{resp.status_code}", resp.status_code
    except Exception as exc:  # noqa: BLE001
        return False, str(exc), None


def deliver_event(tenant_id: str, event: str, payload: dict) -> list[dict]:
    """Enqueue + attempt immediate delivery; failures stay in durable queue."""
    delivery_ids = enqueue_event(tenant_id, event, payload)
    return process_pending_deliveries(limit=len(delivery_ids) or 10, tenant_id=tenant_id)


def process_pending_deliveries(
    *, limit: int = 50, tenant_id: str | None = None
) -> list[dict]:
    """Worker drain: exponential backoff retry for pending/failed deliveries."""
    settings = get_settings()
    max_attempts = settings.webhook_max_attempts
    now = datetime.now(UTC)
    results: list[dict] = []

    # Admin scan across tenants for worker; per-tenant when tenant_id set
    with session_scope(admin=True) as session:
        q = select(WebhookDelivery).where(
            WebhookDelivery.status.in_(["pending", "retry"]),
            WebhookDelivery.next_attempt_at <= now,
        )
        if tenant_id:
            q = q.where(WebhookDelivery.tenant_id == UUID(tenant_id))
        rows = list(session.scalars(q.order_by(WebhookDelivery.next_attempt_at).limit(limit)).all())

        for row in rows:
            sub = session.get(WebhookSubscription, row.subscription_id)
            if sub is None or not sub.active:
                row.status = "cancelled"
                results.append({"id": str(row.id), "ok": False, "error": "subscription_gone"})
                continue

            ok, err, status = _attempt_http(sub, row.event, row.payload or {})
            row.attempts = (row.attempts or 0) + 1
            sub.last_delivery_at = now
            if ok:
                row.status = "delivered"
                row.delivered_at = now
                row.last_error = None
                results.append({"id": str(row.id), "status": status, "ok": True})
            else:
                sub.failure_count = (sub.failure_count or 0) + 1
                row.last_error = err
                if row.attempts >= max_attempts:
                    row.status = "dead"
                else:
                    row.status = "retry"
                    delay = _BACKOFF[min(row.attempts - 1, len(_BACKOFF) - 1)]
                    row.next_attempt_at = now + timedelta(seconds=delay)
                results.append({"id": str(row.id), "ok": False, "error": err, "attempts": row.attempts})
    return results
