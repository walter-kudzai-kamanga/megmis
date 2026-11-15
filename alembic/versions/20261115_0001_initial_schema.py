"""initial megmis schema with postgis

Revision ID: 20261115_0001
Revises:
Create Date: 2026-11-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "20261115_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("plan", sa.String(50), server_default="free"),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("settings", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("hashed_key", sa.String(64), nullable=False, unique=True),
        sa.Column("prefix", sa.String(32), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("label", sa.String(100), server_default="default"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("geom", Geometry(geometry_type="POINT", srid=4326)),
        sa.Column("admin_area", sa.String(200)),
        sa.UniqueConstraint("tenant_id", "name", name="uq_location_tenant_name"),
    )
    op.create_index("ix_locations_geom", "locations", ["geom"], postgresql_using="gist")

    op.create_table(
        "routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("origin_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id")),
        sa.Column("destination_location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id")),
        sa.Column("waypoints", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("profile", sa.String(50), server_default="safest"),
        sa.Column("vehicle_class", sa.String(50), server_default="car"),
        sa.Column("departure_time", sa.DateTime(timezone=True)),
        sa.Column("result", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_routes_tenant_created", "routes", ["tenant_id", "created_at"])

    op.create_table(
        "journeys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("routes.id"), nullable=False),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("current_lat", sa.Float()),
        sa.Column("current_lon", sa.Float()),
        sa.Column("current_position", Geometry(geometry_type="POINT", srid=4326)),
        sa.Column("monitored_route", Geometry(geometry_type="LINESTRING", srid=4326)),
        sa.Column("alert_subscriptions", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("snapshot", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_journeys_current_position", "journeys", ["current_position"], postgresql_using="gist")
    op.create_index("ix_journeys_monitored_route", "journeys", ["monitored_route"], postgresql_using="gist")

    op.create_table(
        "road_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id")),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("severity", sa.Integer(), server_default="1"),
        sa.Column("confidence", sa.Float(), server_default="0.4"),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("reporter_ref", sa.String(100)),
        sa.Column("evidence_refs", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("area", sa.String(200)),
        sa.Column("lat", sa.Float()),
        sa.Column("lon", sa.Float()),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("corroboration_count", sa.Integer(), server_default="0"),
    )

    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(50), server_default="crowdsourced"),
        sa.Column("road_report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("road_reports.id")),
        sa.Column("geom", Geometry(geometry_type="GEOMETRY", srid=4326)),
        sa.Column("lat", sa.Float()),
        sa.Column("lon", sa.Float()),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("severity", sa.Integer(), server_default="1"),
        sa.Column("confidence", sa.Float(), server_default="0.5"),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(50), server_default="active"),
        sa.Column("area", sa.String(200)),
        sa.Column("verified", sa.Boolean(), server_default=sa.text("false")),
    )
    op.create_index("ix_incidents_geom", "incidents", ["geom"], postgresql_using="gist")
    op.execute(
        "CREATE INDEX ix_incidents_active ON incidents (status) WHERE status = 'active'"
    )

    op.create_table(
        "weather_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("locations.id")),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_official_warning", sa.Boolean(), server_default=sa.text("false")),
    )

    op.create_table(
        "risk_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("subject_type", sa.String(50), nullable=False),
        sa.Column("subject_id", sa.String(100), nullable=False),
        sa.Column("activity", sa.String(100)),
        sa.Column("score", sa.Float(), server_default="0"),
        sa.Column("level", sa.String(50), server_default="low"),
        sa.Column("indicators", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("recommendations", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb")),
        sa.Column("confidence", sa.String(50), server_default="medium"),
        sa.Column("data_sources", postgresql.ARRAY(sa.Text()), server_default="{}"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id")),
        sa.Column("actor", sa.String(200), server_default="system"),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource", sa.String(200)),
        sa.Column("request_id", sa.String(100)),
        sa.Column("ip", sa.String(64)),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_tenant_ts", "audit_log", ["tenant_id", "ts"])

    # Gen 1 scaffold RLS (enforced more strictly in Gen 2)
    for table in ("routes", "journeys", "road_reports", "risk_assessments", "api_keys"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (tenant_id::text = current_setting('app.tenant_id', true))
            """
        )


def downgrade() -> None:
    for table in ("routes", "journeys", "road_reports", "risk_assessments", "api_keys"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    for table in (
        "audit_log",
        "risk_assessments",
        "weather_snapshots",
        "incidents",
        "road_reports",
        "journeys",
        "routes",
        "locations",
        "api_keys",
        "tenants",
    ):
        op.drop_table(table)
