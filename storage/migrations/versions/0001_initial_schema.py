"""Initial schema: pgvector extension + obligations, findings, obligation_embeddings.

The enum value lists in the CHECK constraints mirror the Literals in
contracts/models.py (which mirror dataset/taxonomy.json). If the taxonomy
grows, add a follow-up migration altering the constraint.

Revision ID: 0001
Revises:
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_FAMILIES = (
    "'rohs', 'reach', 'weee', 'battery', 'ppwr', 'gpsr', 'red', 'espr', "
    "'toy_safety', 'mdr', 'pops', 'epr', 'epr_packaging', 'energy_label', "
    "'emc', 'lvd', 'machinery', 'atex', 'chemical_safety', 'cybersecurity', 'other'"
)
_CHANGE_TYPES = "'new', 'amendment', 'correction'"
_SEVERITIES = "'low', 'medium', 'high'"
_CHANNELS = "'email', 'sms', 'whatsapp'"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "obligations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("update_id", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("celex", sa.Text(), nullable=True),
        sa.Column("consolidation_date", sa.Date(), nullable=True),
        sa.Column("access_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("regulation_family", sa.Text(), nullable=False),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("action_required", sa.Text(), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("deadline_date", sa.Date(), nullable=True),
        sa.Column("scope_all_categories", sa.Boolean(), nullable=False),
        sa.Column("scope_categories", ARRAY(sa.Text()), nullable=False),
        sa.Column("scope_substances", ARRAY(sa.Text()), nullable=False),
        sa.Column("scope_markets", ARRAY(sa.Text()), nullable=False),
        sa.Column("scope_conditions", sa.Text(), nullable=False),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_id", sa.BigInteger(), sa.ForeignKey("obligations.id"), nullable=True),
        sa.Column("corrects_update_id", sa.Text(), nullable=True),
        sa.CheckConstraint("source_url <> ''", name="ck_obligations_source_url_nonempty"),
        sa.CheckConstraint(
            f"regulation_family IN ({_FAMILIES})", name="ck_obligations_regulation_family"
        ),
        sa.CheckConstraint(f"change_type IN ({_CHANGE_TYPES})", name="ck_obligations_change_type"),
        sa.CheckConstraint(f"severity IN ({_SEVERITIES})", name="ck_obligations_severity"),
    )
    op.create_index("ix_obligations_update_id", "obligations", ["update_id"])
    op.create_index("ix_obligations_regulation_family", "obligations", ["regulation_family"])
    op.create_index("ix_obligations_in_force", "obligations", ["valid_to"])

    op.create_table(
        "findings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "assessed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("obligation_id", sa.BigInteger(), sa.ForeignKey("obligations.id"), nullable=True),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("partner_id", sa.Text(), nullable=False),
        sa.Column("product_id", sa.Text(), nullable=False),
        sa.Column("product", sa.Text(), nullable=False),
        sa.Column("regulation", sa.Text(), nullable=False),
        sa.Column("requirement", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("gap", sa.Text(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("alert_channel", sa.Text(), nullable=False),
        sa.Column("alert_to", sa.Text(), nullable=False),
        sa.Column("alert_message", sa.Text(), nullable=False),
        sa.CheckConstraint("source_url <> ''", name="ck_findings_source_url_nonempty"),
        sa.CheckConstraint(f"severity IN ({_SEVERITIES})", name="ck_findings_severity"),
        sa.CheckConstraint(f"alert_channel IN ({_CHANNELS})", name="ck_findings_alert_channel"),
    )
    op.create_index("ix_findings_partner_product", "findings", ["partner_id", "product_id"])

    op.create_table(
        "obligation_embeddings",
        sa.Column(
            "obligation_id",
            sa.BigInteger(),
            sa.ForeignKey("obligations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("embedding", Vector(256), nullable=False),
        sa.Column("embedder", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("obligation_embeddings")
    op.drop_index("ix_findings_partner_product", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_obligations_in_force", table_name="obligations")
    op.drop_index("ix_obligations_regulation_family", table_name="obligations")
    op.drop_index("ix_obligations_update_id", table_name="obligations")
    op.drop_table("obligations")
    op.execute("DROP EXTENSION IF EXISTS vector")
