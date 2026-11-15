"""Gen 3: agent sessions, audio artefacts, voice training utterances

Revision ID: 20261115_0004
Revises: 20261115_0003
Create Date: 2026-11-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261115_0004"
down_revision: Union[str, None] = "20261115_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("channel", sa.String(50), server_default="ws"),
        sa.Column("state", sa.String(50), server_default="active"),
        sa.Column("lang", sa.String(20), server_default="en"),
        sa.Column("scenario", sa.String(100)),
        sa.Column("transcript_ref", sa.String(500)),
        sa.Column("meta", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_agent_sessions_tenant", "agent_sessions", ["tenant_id", "started_at"])

    op.create_table(
        "audio_artefacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(50), nullable=False),  # stt_in | tts_out | training
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("lang", sa.String(20)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("meta", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audio_session", "audio_artefacts", ["session_id"])

    op.create_table(
        "voice_training_utterances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("lang", sa.String(20), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("expected_intent", sa.String(100)),
        sa.Column("transcript", sa.Text()),
        sa.Column("wer", sa.Float()),
        sa.Column("audio_path", sa.String(500)),
        sa.Column("score", sa.Float()),
        sa.Column("meta", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_voice_train_tenant", "voice_training_utterances", ["tenant_id", "created_at"])

    for table in ("agent_sessions", "audio_artefacts", "voice_training_utterances"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            FOR ALL
            USING (tenant_id::text = current_setting('app.tenant_id', true))
            WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true))
            """
        )
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO megmis_app")


def downgrade() -> None:
    for table in ("voice_training_utterances", "audio_artefacts", "agent_sessions"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.drop_table(table)
