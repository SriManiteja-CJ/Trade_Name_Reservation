"""
tests/test_sync_worker.py
Unit tests for Stage ⑦ Index Sync Worker (index/sync_worker.py).

Spec references:
  F15 — Reliable index sync using transactional outbox pattern
  F21 — Status updates and deletions reflected in TradeNameIndex
"""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db.models import NameIndexOutbox, TradeNameIndex
from index.repository import TradeNameIndexRepository
from index.sync_worker import process_outbox_batch


@pytest.mark.asyncio
async def test_sync_worker_delete_operation(db_session: AsyncSession):
    session_factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False, class_=AsyncSession)
    repo = TradeNameIndexRepository(db_session)

    # Seed index item
    await repo.upsert(
        trade_name_id=888,
        normalized_ar="شركه ملغاه",
        normalized_en="cancelled company",
        phonetic_key="MLG|CNCL",
        status="active",
    )
    await db_session.commit()

    # Seed delete outbox row
    outbox_entry = NameIndexOutbox(
        trade_name_id=888,
        operation="delete",
    )
    db_session.add(outbox_entry)
    await db_session.commit()

    # Run outbox batch
    count = await process_outbox_batch(session_factory)
    assert count == 1

    # Verify TradeNameIndex has deleted entry
    remaining = await repo.lookup_exact("شركه ملغاه", "cancelled company")
    assert len(remaining) == 0

    # Verify outbox row marked processed
    stmt = select(NameIndexOutbox).where(NameIndexOutbox.trade_name_id == 888)
    res = await db_session.execute(stmt)
    outbox_row = res.scalar_one()
    assert outbox_row.processed_on is not None


@pytest.mark.asyncio
async def test_sync_worker_insert_operation(db_session: AsyncSession):
    session_factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False, class_=AsyncSession)

    outbox_entry = NameIndexOutbox(
        trade_name_id=999,
        operation="insert",
    )
    db_session.add(outbox_entry)
    await db_session.commit()

    fake_master = {
        "name_ar": "شركة المستقبل",
        "name_en": "Future Company",
        "status": "active",
        "category_id": 5,
        "expiry_date": None,
    }

    with patch("index.sync_worker._fetch_master_record", new_callable=AsyncMock, return_value=fake_master), \
         patch("index.sync_worker.get_embeddings", new_callable=AsyncMock, return_value=(None, None)):
        count = await process_outbox_batch(session_factory)
        assert count == 1

    # Verify record in index
    repo = TradeNameIndexRepository(db_session)
    matches = await repo.lookup_exact("شركه المستقبل", "future company")
    assert len(matches) == 1
    assert matches[0].trade_name_id == 999
