from __future__ import annotations

import logging
from uuid import UUID

from megmis.db.models import AuditLog
from megmis.db.session import session_scope

logger = logging.getLogger("megmis.security")


def write_audit(
    *,
    action: str,
    actor: str = "system",
    tenant_id: UUID | str | None = None,
    resource: str | None = None,
    request_id: str | None = None,
    ip: str | None = None,
    security: bool = False,
) -> None:
    tid = UUID(str(tenant_id)) if tenant_id else None
    try:
        with session_scope(admin=True) as session:
            session.add(
                AuditLog(
                    tenant_id=tid,
                    actor=actor,
                    action=action,
                    resource=resource,
                    request_id=request_id,
                    ip=ip,
                )
            )
    except Exception:
        logger.exception("audit_write_failed action=%s", action)

    if security:
        logger.warning(
            "security_event action=%s actor=%s tenant=%s resource=%s request_id=%s",
            action,
            actor,
            tenant_id,
            resource,
            request_id,
        )
