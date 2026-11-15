"""Gen 2 hardening: durable webhook delivery queue

Revision ID: 20261115_0003
Revises: 20261115_0002
Create Date: 2026-11-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261115_0003"
down_revision: Union[str, None] = "20261115_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("attempts", sa.Integer(), server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_webhook_deliveries_pending",
        "webhook_deliveries",
        ["status", "next_attempt_at"],
    )
    op.create_index("ix_webhook_deliveries_tenant", "webhook_deliveries", ["tenant_id"])

    op.execute("ALTER TABLE webhook_deliveries ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_webhook_deliveries ON webhook_deliveries
        FOR ALL
        USING (tenant_id::text = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true))
        """
    )
    op.execute("ALTER TABLE webhook_deliveries FORCE ROW LEVEL SECURITY")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON webhook_deliveries TO megmis_app"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_webhook_deliveries ON webhook_deliveries")
    op.drop_table("webhook_deliveries")
