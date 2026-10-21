"""
tests/test_index_repository.py
Integration tests for TradeNameIndexRepository (index/repository.py).

Spec references:
  F2  — Exact duplicate check
  F15 — Index sync and maintenance
  F19 — Search lookup
  F21 — Status active filtering
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from index.repository import TradeNameIndexRepository


@pytest.mark.asyncio
async def test_index_upsert_and_lookup_exact(db_session: AsyncSession):
    repo = TradeNameIndexRepository(db_session)

    await repo.upsert(
        trade_name_id=501,
        normalized_ar="شركه الصقر",
        normalized_en="falcon company",
        phonetic_key="SKR|SKR",
        status="active",
        category_id=12,
    )

    # Exact match on Arabic
    ar_matches = await repo.lookup_exact(
        normalized_ar="شركه الصقر",
        normalized_en="different name",
    )
    assert len(ar_matches) == 1
    assert ar_matches[0].trade_name_id == 501

    # Exact match on English
    en_matches = await repo.lookup_exact(
        normalized_ar="اسم مختلف",
        normalized_en="falcon company",
    )
    assert len(en_matches) == 1
    assert en_matches[0].trade_name_id == 501

    # Exclude self by trade_name_id
    excluded = await repo.lookup_exact(
        normalized_ar="شركه الصقر",
        normalized_en="falcon company",
        exclude_trade_name_id=501,
    )
    assert len(excluded) == 0


@pytest.mark.asyncio
async def test_index_status_filter_active_only(db_session: AsyncSession):
    repo = TradeNameIndexRepository(db_session)

    # Upsert expired/released record
    await repo.upsert(
        trade_name_id=502,
        normalized_ar="شركه قديمه",
        normalized_en="old company",
        phonetic_key="QDM|OLD",
        status="expired",
    )

    matches = await repo.lookup_exact(
        normalized_ar="شركه قديمه",
        normalized_en="old company",
    )
    assert len(matches) == 0


@pytest.mark.asyncio
async def test_index_phonetic_lookup(db_session: AsyncSession):
    repo = TradeNameIndexRepository(db_session)

    await repo.upsert(
        trade_name_id=503,
        normalized_ar="نور",
        normalized_en="noor",
        phonetic_key="NWR|NUR",
        status="active",
    )

    results = await repo.lookup_phonetic("NWR|NUR")
    assert len(results) == 1
    assert results[0].trade_name_id == 503


@pytest.mark.asyncio
async def test_index_delete(db_session: AsyncSession):
    repo = TradeNameIndexRepository(db_session)

    await repo.upsert(
        trade_name_id=504,
        normalized_ar="شركه للحذف",
        normalized_en="delete company",
        phonetic_key="DEL|DEL",
        status="active",
    )

    await repo.delete(504)

    matches = await repo.lookup_exact(
        normalized_ar="شركه للحذف",
        normalized_en="delete company",
    )
    assert len(matches) == 0
