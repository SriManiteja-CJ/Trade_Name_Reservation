"""
db/models.py
SQLAlchemy 2.0 declarative ORM models for all 6 new tables specified in spec §5.1.

Tables created:
  1. TradeNameIndex   — fast exact, phonetic and vector lookup of active names
  2. Lexicon          — managed word lists for F4 checks
  3. NameIndexOutbox  — reliable index sync (F15, transactional outbox pattern)
  4. AiDecisionAudit  — audit trail for every LLM call (N3)
  5. ReviewerBrief    — copilot output and reviewer feedback (E5, N7)
  6. PromptVersion    — versioned LLM prompts

IMPORTANT: This migration is non-destructive to the existing DED schema.
  All new tables are isolated; no existing tables are modified.

Embedding dimension defaults to 768 (intfloat/multilingual-e5-base).
Update EMBEDDING_DIM before the first migration if a different model is chosen (Ambiguity #1).
"""
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Embedding dimension constant (Ambiguity #1 — update to match deployed model)
# ---------------------------------------------------------------------------
EMBEDDING_DIM: int = 768


class Base(DeclarativeBase):
    """Shared declarative base for all TNIS ORM models."""
    pass


# ---------------------------------------------------------------------------
# 1. TradeNameIndex
#    Fast exact, phonetic and vector lookup of active trade names.
#    Populated and maintained by the Index Sync Worker (Stage ⑦).
#    Spec §5.1 columns: Id, NormalizedAr, NormalizedEn, PhoneticKey,
#      EmbeddingAr, EmbeddingEn, CategoryId, Status, ExpiryDate
# ---------------------------------------------------------------------------
class TradeNameIndex(Base):
    __tablename__ = "trade_name_index"

    id: Mapped[int] = mapped_column(Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True)

    # FK to the existing master trade-name table (read-only reference)
    trade_name_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True, index=True,
        comment="FK to existing master trade-name record"
    )

    # Normalized forms produced by Stage ① Normalizer (spec §3 Component ①)
    normalized_ar: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_en: Mapped[str] = mapped_column(Text, nullable=False)

    # Cross-script phonetic key produced by index/phonetic.py (E2)
    phonetic_key: Mapped[str] = mapped_column(String(512), nullable=False)

    # Multilingual embedding vectors — stored as raw bytes; pgvector extension
    # handles VECTOR(768) type via the migration DDL (not via SQLAlchemy type).
    # We store as Text here and rely on the Alembic migration to set the
    # correct VECTOR column type using server_default / literal DDL.
    # In queries we use text() to cast to ::vector.
    embedding_ar: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="pgvector VECTOR(768) — overridden in Alembic migration"
    )
    embedding_en: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="pgvector VECTOR(768) — overridden in Alembic migration"
    )

    # Activity category (Gap #1: single category_id; plural codes TBD)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Canonical extracted base names used for atomic, activity-scoped reservation.
    base_name_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_name_ar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status values: active | released | expired | draft
    # Only 'active' records participate in F2 (exact dup) and F3 (similarity).
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )

    # Composite indexes (B-tree on normalized forms, GIN trigram, phonetic)
    # ivfflat vector indexes created in Alembic migration via literal DDL.
    __table_args__ = (
        Index("idx_tni_normalized_ar", "normalized_ar"),
        Index("idx_tni_normalized_en", "normalized_en"),
        Index("idx_tni_phonetic", "phonetic_key"),
        Index("idx_tni_category_id", "category_id"),
        Index(
            "uq_tni_active_cat_norm_en",
            "category_id",
            "normalized_en",
            unique=True,
            postgresql_where=text("status = 'active' AND normalized_en != ''"),
            sqlite_where=text("status = 'active' AND normalized_en != ''"),
        ),
        Index(
            "uq_tni_active_cat_norm_ar",
            "category_id",
            "normalized_ar",
            unique=True,
            postgresql_where=text("status = 'active' AND normalized_ar != ''"),
            sqlite_where=text("status = 'active' AND normalized_ar != ''"),
        ),
        Index(
            "uq_tni_active_cat_base_en",
            "category_id",
            "base_name_en",
            unique=True,
            postgresql_where=text("status IN ('active', 'reserved') AND category_id IS NOT NULL AND base_name_en IS NOT NULL AND base_name_en != ''"),
            sqlite_where=text("status IN ('active', 'reserved') AND category_id IS NOT NULL AND base_name_en IS NOT NULL AND base_name_en != ''"),
        ),
        Index(
            "uq_tni_active_cat_base_ar",
            "category_id",
            "base_name_ar",
            unique=True,
            postgresql_where=text("status IN ('active', 'reserved') AND category_id IS NOT NULL AND base_name_ar IS NOT NULL AND base_name_ar != ''"),
            sqlite_where=text("status IN ('active', 'reserved') AND category_id IS NOT NULL AND base_name_ar IS NOT NULL AND base_name_ar != ''"),
        ),
    )


# ---------------------------------------------------------------------------
# 2. Lexicon
#    Managed word lists for F4 word checks.
#    Categories map to legacy response fields:
#      prohibited → Prohibted (sic)
#      profanity  → Profanity
#      unfriendly → Unfriendly
#      special    → Special
#      divine_name → AllahNames
#      location   → LocationNames
#      family_name → FamilyNames
#    Additional LLM-only categories (not stored in lexicon):
#      impersonation, misleading  (semantic risk, not lexicon-based)
# ---------------------------------------------------------------------------
class Lexicon(Base):
    __tablename__ = "lexicon"

    id: Mapped[int] = mapped_column(Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True)

    term: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_term: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # F4 category — one of the 7 managed categories
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="prohibited|profanity|unfriendly|special|divine_name|location|family_name"
    )

    # Language scope of the term
    lang: Mapped[str] = mapped_column(
        String(8), nullable=False,
        comment="ar|en|both"
    )

    # Determines outcome in Stage ②: block → BLOCKED, review → NEEDS_REVIEW, info → logged
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="block|review|info"
    )

    # JSON array of variant strings (alternate spellings, Arabizi, etc.)
    # Populated by Stage ⑨ after admin approval (E7)
    variants: Mapped[Optional[Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    # DED employee who approved this entry (null = system-seeded / pending)
    approved_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("normalized_term", "category", "lang", name="uq_lexicon_term_cat_lang"),
    )


# ---------------------------------------------------------------------------
# 3. NameIndexOutbox
#    Transactional outbox for reliable index sync (F15).
#    CRITICAL: outbox rows MUST be written in the same DB transaction
#    as the trade-name insert/update/delete in the master table.
# ---------------------------------------------------------------------------
class NameIndexOutbox(Base):
    __tablename__ = "name_index_outbox"

    id: Mapped[int] = mapped_column(Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True)
    trade_name_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # insert | update | delete
    operation: Mapped[str] = mapped_column(String(16), nullable=False)

    created_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Null = unprocessed; set by sync worker after successful processing
    processed_on: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # Partial index for efficient unprocessed-row polling
        Index(
            "idx_outbox_unprocessed",
            "processed_on",
            postgresql_where="processed_on IS NULL",
        ),
    )


# ---------------------------------------------------------------------------
# 4. AiDecisionAudit
#    Audit trail for every LLM call (N3).
#    request_id = real DED application request ID (not a random UUID).
#    Written by the LLM Gateway after every call (success or failure).
# ---------------------------------------------------------------------------
class AiDecisionAudit(Base):
    __tablename__ = "ai_decision_audit"

    id: Mapped[int] = mapped_column(Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True)

    # Real DED application request ID (N3 — "linked to the real request ID")
    request_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    channel: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="online|walkin"
    )

    # SHA-256 of the normalized input pair + category + legal_form (N6 — no raw PII stored)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Prompt version name at time of call (spec §4.3 — versioned prompts)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)

    # Model identifier (vLLM model name)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)

    # Raw LLM JSON output (null if LLM was unavailable)
    raw_output: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    # Decision outcome at time of this audit entry
    outcome: Mapped[str] = mapped_column(
        String(16), nullable=False,
        comment="OK|NEEDS_REVIEW|BLOCKED"
    )

    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# 5. ReviewerBrief
#    Copilot output per submission (E5) and reviewer feedback for N7.
# ---------------------------------------------------------------------------
class ReviewerBrief(Base):
    __tablename__ = "reviewer_brief"

    id: Mapped[int] = mapped_column(Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True)

    # One brief per submission
    request_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Structured brief: flags, top-5 similar, transliteration verdict,
    # activity fit verdict, recommendation, draft AdminComments (AR + EN)
    brief_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)

    generated_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Filled after reviewer acts — used for N7 quality feedback loop
    reviewer_decision: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True,
        comment="approve|reject|return|ssp_committee"
    )

    __table_args__ = (UniqueConstraint("request_id", name="uq_reviewer_brief_request_id"),)


# ---------------------------------------------------------------------------
# 6. PromptVersion
#    Versioned LLM prompts (spec §4.3 — "prompts are versioned; the version
#    is stored with every audit record").
#    Only one row per name should have active=True at any time.
# ---------------------------------------------------------------------------
class PromptVersion(Base):
    __tablename__ = "prompt_version"

    id: Mapped[int] = mapped_column(Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True)

    # Human-readable name, e.g. "analyzer_v1", "suggestions_v2"
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # Full prompt text (system prompt content)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    created_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_prompt_version_name_active", "name", "active"),
    )
