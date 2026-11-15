"""Gen 4 commercial: GPS traces, calibrations, object artefacts

Revision ID: 20261115_0005
Revises: 20261115_0004
Create Date: 2026-11-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261115_0005"
down_revision: Union[str, None] = "20261115_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gps_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("routes.id"), nullable=True),
        sa.Column("profile", sa.String(50), server_default="safest"),
        sa.Column("distance_m", sa.Float(), server_default="0"),
        sa.Column("duration_s", sa.Float(), server_default="0"),
        sa.Column("mean_speed_mps", sa.Float(), server_default="0"),
        sa.Column("points", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("meta", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_gps_traces_tenant", "gps_traces", ["tenant_id", "created_at"])

    op.create_table(
        "cost_calibrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("profile", sa.String(50), nullable=False),
        sa.Column("trace_count", sa.Integer(), server_default="0"),
        sa.Column("weights_before", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("weights_after", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("features", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_cost_cal_tenant", "cost_calibrations", ["tenant_id", "profile"])

    op.create_table(
        "object_artefacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("key", sa.String(500), nullable=False),
        sa.Column("uri", sa.String(700), nullable=False),
        sa.Column("kind", sa.String(50), server_default="audio"),
        sa.Column("content_type", sa.String(100), server_default="application/octet-stream"),
        sa.Column("bytes", sa.Integer(), server_default="0"),
        sa.Column("retention_days", sa.Integer(), server_default="30"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("meta", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_object_artefacts_tenant", "object_artefacts", ["tenant_id", "expires_at"])

    for table in ("gps_traces", "cost_calibrations", "object_artefacts"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            FOR ALL
            USING (tenant_id::text = current_setting('app.tenant_id', true))
            WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true))
            """
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO megmis_app")


def downgrade() -> None:
    for table in ("object_artefacts", "cost_calibrations", "gps_traces"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.drop_table(table)
