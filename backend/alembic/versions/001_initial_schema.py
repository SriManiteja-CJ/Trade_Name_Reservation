"""Initial migration: 6 TNIS tables, pgvector, pg_trgm

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-10-06 23:58:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable required extensions if PostgreSQL
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. Table: trade_name_index
    op.create_table(
        "trade_name_index",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trade_name_id", sa.BigInteger(), nullable=False),
        sa.Column("normalized_ar", sa.Text(), nullable=False),
        sa.Column("normalized_en", sa.Text(), nullable=False),
        sa.Column("phonetic_key", sa.String(length=512), nullable=False),
        sa.Column("embedding_ar", sa.Text(), nullable=True),
        sa.Column("embedding_en", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trade_name_id"),
    )
    op.create_index("idx_tni_normalized_ar", "trade_name_index", ["normalized_ar"])
    op.create_index("idx_tni_normalized_en", "trade_name_index", ["normalized_en"])
    op.create_index("idx_tni_phonetic", "trade_name_index", ["phonetic_key"])
    op.create_index("idx_tni_status", "trade_name_index", ["status"])

    if conn.dialect.name == "postgresql":
        # Specific vector & gin indexes
        op.execute("CREATE INDEX IF NOT EXISTS idx_tni_trgm_ar ON trade_name_index USING gin (normalized_ar gin_trgm_ops);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_tni_trgm_en ON trade_name_index USING gin (normalized_en gin_trgm_ops);")

    # 3. Table: lexicon
    op.create_table(
        "lexicon",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("normalized_term", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("lang", sa.String(length=8), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("variants", postgresql.JSONB(astext_type=sa.Text()) if conn.dialect.name == "postgresql" else sa.JSON(), nullable=True),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_term", "category", "lang", name="uq_lexicon_term_cat_lang"),
    )
    op.create_index("idx_lexicon_normalized", "lexicon", ["normalized_term"])
    op.create_index("idx_lexicon_category", "lexicon", ["category"])

    # 4. Table: name_index_outbox
    op.create_table(
        "name_index_outbox",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trade_name_id", sa.BigInteger(), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("created_on", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_on", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_outbox_unprocessed", "name_index_outbox", ["processed_on"])

    # 5. Table: ai_decision_audit
    op.create_table(
        "ai_decision_audit",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("raw_output", postgresql.JSONB(astext_type=sa.Text()) if conn.dialect.name == "postgresql" else sa.JSON(), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_request_id", "ai_decision_audit", ["request_id"])

    # 6. Table: reviewer_brief
    op.create_table(
        "reviewer_brief",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("brief_json", postgresql.JSONB(astext_type=sa.Text()) if conn.dialect.name == "postgresql" else sa.JSON(), nullable=False),
        sa.Column("generated_on", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewer_decision", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("idx_brief_request_id", "reviewer_brief", ["request_id"])

    # 7. Table: prompt_version
    op.create_table(
        "prompt_version",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_on", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_prompt_version_name", "prompt_version", ["name", "active"])


def downgrade() -> None:
    op.drop_table("prompt_version")
    op.drop_table("reviewer_brief")
    op.drop_table("ai_decision_audit")
    op.drop_table("name_index_outbox")
    op.drop_table("lexicon")
    op.drop_table("trade_name_index")
