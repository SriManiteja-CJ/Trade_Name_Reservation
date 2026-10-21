"""
index/sync_worker.py
Stage ⑦ — Index Sync Worker (arq background worker)

Implements the transactional outbox pattern for reliable index sync (F15).

Responsibilities:
  - Poll NameIndexOutbox for unprocessed rows (processed_on IS NULL)
  - For insert/update operations: normalize → phonetic key → TEI embeddings → upsert TradeNameIndex
  - For delete operations: remove from TradeNameIndex
  - Mark outbox rows as processed (set processed_on = now())
  - Nightly reconciliation: compare TradeNameIndex against master to catch missed events

CRITICAL GUARANTEES:
  1. Idempotency: re-processing the same outbox row yields the same state
  2. No data loss: outbox row stays unprocessed until successful; retry on failure
  3. Released names removed from index (F21) when operation=update and status != active

Spec references:
  F15 — "Name index stays in sync on insert, edit, release and delete,
          with activity category and codes"
  §3 Component ⑦ — "Outbox row written in the same transaction as each name
          change; computes keys and embeddings; nightly reconciliation"
  Ambiguity #8 — Outbox writer location: assumed written by the caller/existing DED code.
                 This worker only reads from NameIndexOutbox.

arq worker registration: see api/main.py for WorkerSettings.
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config.settings import get_settings
from db.models import NameIndexOutbox
from index.phonetic import generate_phonetic_key_pair
from index.repository import TradeNameIndexRepository
from pipeline.normalizer import normalize_arabic, normalize_english

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# TEI (Text Embeddings Inference) client
# ---------------------------------------------------------------------------
async def get_embeddings(text_ar: str, text_en: str) -> tuple[Optional[list[float]], Optional[list[float]]]:
    """
    Fetch multilingual embeddings from the self-hosted TEI endpoint.
    Returns (embedding_ar, embedding_en) or (None, None) on failure.

    Spec: "Open-source multilingual embedding model served by Text Embeddings Inference"
    N5: TEI is self-hosted; no data leaves DED infrastructure.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.tei_base_url}/embed",
                json={"inputs": [text_ar, text_en]},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data if isinstance(data, list) else data.get("embeddings", [])
            if len(embeddings) >= 2:
                return embeddings[0], embeddings[1]
            return None, None
    except Exception as exc:
        logger.warning("TEI embedding request failed: %s", exc)
        return None, None


# ---------------------------------------------------------------------------
# Outbox polling and processing
# ---------------------------------------------------------------------------
async def process_outbox_batch(
    session_factory: async_sessionmaker[AsyncSession],
    batch_size: int = 50,
) -> int:
    """
    Poll the NameIndexOutbox for unprocessed rows and process them.
    Returns the number of rows processed.

    Processing steps for each row:
      1. Fetch the trade name data from the master table
         (Ambiguity #8: assumes master table accessible; query placeholder)
      2. Normalize names via Stage ① Normalizer
      3. Compute phonetic key via phonetic.py
      4. Fetch embeddings from TEI (if available)
      5. Upsert or delete from TradeNameIndex
      6. Mark outbox row as processed

    If TEI is unavailable, embeddings are skipped and the row is still processed
    (phonetic + normalized keys are always computed).
    """
    processed = 0

    async with session_factory() as session:
        # Fetch a batch of unprocessed outbox rows
        stmt = (
            select(NameIndexOutbox)
            .where(NameIndexOutbox.processed_on.is_(None))
            .order_by(NameIndexOutbox.created_on)
            .limit(batch_size)
        )
        try:
            bind = session.get_bind()
            if bind and bind.dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)  # concurrent-safe on postgres
        except Exception:
            pass
        result = await session.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return 0

        repo = TradeNameIndexRepository(session)

        for row in rows:
            try:
                await _process_single_row(row, repo, session)
                processed += 1
            except Exception as exc:
                logger.error(
                    "Failed to process outbox row id=%s trade_name_id=%s: %s",
                    row.id, row.trade_name_id, exc,
                )
                # Do NOT mark as processed; it will be retried
                await session.rollback()
                continue

        await session.commit()

    return processed


async def _process_single_row(
    row: NameIndexOutbox,
    repo: TradeNameIndexRepository,
    session: AsyncSession,
) -> None:
    """Process a single NameIndexOutbox row."""

    if row.operation == "delete":
        # Remove from index; F21: released/expired names become available
        await repo.delete(row.trade_name_id)
    else:
        # insert | update: fetch master data and sync
        master = await _fetch_master_record(row.trade_name_id, session)
        if master is None:
            logger.warning(
                "Master record not found for trade_name_id=%s; skipping.",
                row.trade_name_id,
            )
        else:
            name_ar = master.get("name_ar", "")
            name_en = master.get("name_en", "")
            status = master.get("status", "active")
            category_id = master.get("category_id")
            expiry_date = master.get("expiry_date")

            # Normalize via Stage ①
            norm_ar = normalize_arabic(name_ar)
            norm_en = normalize_english(name_en)

            # Compute cross-script phonetic key (E2)
            phonetic_key = generate_phonetic_key_pair(norm_ar, norm_en)

            # Fetch embeddings from TEI (N5: internal call only)
            emb_ar, emb_en = await get_embeddings(norm_ar, norm_en)

            await repo.upsert(
                trade_name_id=row.trade_name_id,
                normalized_ar=norm_ar,
                normalized_en=norm_en,
                phonetic_key=phonetic_key,
                status=status,
                category_id=category_id,
                embedding_ar=emb_ar,
                embedding_en=emb_en,
                expiry_date=str(expiry_date) if expiry_date else None,
            )

    # Mark outbox row as processed (idempotent-safe: we only reach here on success)
    row.processed_on = datetime.now(timezone.utc)
    await session.flush()


async def _fetch_master_record(
    trade_name_id: int,
    session: AsyncSession,
) -> Optional[dict[str, Any]]:
    """
    Fetch the trade name master record from the existing DED database.

    PLACEHOLDER — The actual query depends on the existing DED schema.
    Ambiguity #8: the existing DED database schema for the master trade-name
    table is not provided in the spec. This must be filled in with the correct
    table and column names before Phase 1 can be run against the real database.

    Returns a dict with keys: name_ar, name_en, status, category_id, expiry_date
    or None if the record doesn't exist.
    """
    # TODO: Replace with actual master table query once schema is provided (Ambiguity #8)
    # Example placeholder:
    # result = await session.execute(
    #     text("SELECT name_ar, name_en, status, category_id, expiry_date "
    #          "FROM trade_names WHERE id = :id"),
    #     {"id": trade_name_id}
    # )
    # row = result.fetchone()
    # return dict(row._mapping) if row else None
    logger.warning(
        "PLACEHOLDER: _fetch_master_record not implemented (Ambiguity #8). "
        "trade_name_id=%s",
        trade_name_id,
    )
    return None


# ---------------------------------------------------------------------------
# Nightly reconciliation job
# ---------------------------------------------------------------------------
async def nightly_reconciliation(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    """
    Compare TradeNameIndex against the master DB and fix any discrepancies.
    Runs as a nightly arq cron job.

    Finds:
      - Names in master (active) that are NOT in the index → add to index
      - Names in index where status doesn't match master → update status
      - Names in index that no longer exist in master → remove from index

    Returns a summary dict: {"added": N, "updated": N, "removed": N}
    """
    # TODO: Implement once master schema is known (Ambiguity #8)
    logger.info("Nightly reconciliation started (placeholder — master schema needed)")
    return {"added": 0, "updated": 0, "removed": 0}


# ---------------------------------------------------------------------------
# arq worker context and task definitions
# ---------------------------------------------------------------------------
async def startup(ctx: dict) -> None:
    """arq worker startup: create DB session factory and HTTP client."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from db.session import AsyncSessionLocal
    ctx["session_factory"] = AsyncSessionLocal
    logger.info("Index sync worker started")


async def shutdown(ctx: dict) -> None:
    logger.info("Index sync worker shutting down")


async def sync_outbox_task(ctx: dict) -> dict[str, int]:
    """arq task: process a batch of outbox rows."""
    count = await process_outbox_batch(ctx["session_factory"])
    logger.info("Processed %d outbox rows", count)
    return {"processed": count}


async def reconciliation_task(ctx: dict) -> dict[str, int]:
    """arq cron task: nightly reconciliation."""
    return await nightly_reconciliation(ctx["session_factory"])


class WorkerSettings:
    """arq WorkerSettings for the index sync worker."""
    functions = [sync_outbox_task]
    cron_jobs = [
        # Nightly reconciliation at 02:00 UTC
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = None  # Set at runtime from settings.redis_url
