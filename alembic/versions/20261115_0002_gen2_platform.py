"""Gen 2: webhooks, usage, app role RLS, road pipeline fields

Revision ID: 20261115_0002
Revises: 20261115_0001
Create Date: 2026-11-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261115_0002"
down_revision: Union[str, None] = "20261115_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("events", postgresql.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True)),
        sa.Column("failure_count", sa.Integer(), server_default="0"),
    )
    op.create_index("ix_webhooks_tenant", "webhook_subscriptions", ["tenant_id"])

    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("endpoint", sa.String(200), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("request_id", sa.String(100)),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_usage_tenant_ts", "usage_events", ["tenant_id", "ts"])

    op.create_table(
        "job_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("result", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )

    # Road pipeline enrichment columns
    op.add_column("road_reports", sa.Column("validated_at", sa.DateTime(timezone=True)))
    op.add_column("road_reports", sa.Column("validation_notes", sa.Text()))

    # Strengthen RLS with WITH CHECK + enable on new tables
    for table in ("webhook_subscriptions", "usage_events"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            FOR ALL
            USING (tenant_id::text = current_setting('app.tenant_id', true))
            WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true))
            """
        )

    # Recreate existing policies with WITH CHECK
    for table in ("routes", "journeys", "road_reports", "risk_assessments", "api_keys"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            FOR ALL
            USING (tenant_id::text = current_setting('app.tenant_id', true))
            WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true))
            """
        )

    # Non-superuser app role that cannot bypass RLS
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'megmis_app') THEN
            CREATE ROLE megmis_app LOGIN PASSWORD 'megmis_app' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
          END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO megmis_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO megmis_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO megmis_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO megmis_app"
    )
    # Force RLS even for table owner when using megmis_app
    for table in (
        "routes",
        "journeys",
        "road_reports",
        "risk_assessments",
        "api_keys",
        "webhook_subscriptions",
        "usage_events",
    ):
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in (
        "routes",
        "journeys",
        "road_reports",
        "risk_assessments",
        "api_keys",
        "webhook_subscriptions",
        "usage_events",
    ):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")

    op.drop_column("road_reports", "validation_notes")
    op.drop_column("road_reports", "validated_at")
    op.drop_table("job_runs")
    op.drop_table("usage_events")
    op.drop_table("webhook_subscriptions")
