"""
tests/test_deterministic_gates.py
Integration tests for Stage ② Deterministic Gates (pipeline/deterministic_gates.py).

Spec references:
  F2  — Exact-duplicate check against active names, excluding current record
  F4  — Word checks: 7 categories, severity block | review
  F12 — Unchanged name skips word checks but runs exact duplicate
  F21 — Released/expired names become available again
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from index.repository import TradeNameIndexRepository
from lexicon.repository import LexiconEntry, LexiconRepository
from pipeline.deterministic_gates import DeterministicGates, SignalType
from pipeline.name_composer import compose


@pytest.mark.asyncio
async def test_gate_exact_duplicate_blocks(db_session: AsyncSession):
    index_repo = TradeNameIndexRepository(db_session)
    lexicon_repo = LexiconRepository(db_session)

    # Seed active name in index
    await index_repo.upsert(
        trade_name_id=101,
        normalized_ar="شركه الرواد",
        normalized_en="al rowad company",
        phonetic_key="RWD|RWD",
        status="active",
    )

    composed = compose("شركة الرواد", "Al Rowad Company", operation_type="new")
    gates = DeterministicGates(index_repo, lexicon_repo)
    signals = await gates.run(composed)

    assert any(s.signal_type == SignalType.BLOCKED and s.source == "exact_duplicate" for s in signals)


@pytest.mark.asyncio
async def test_gate_exact_duplicate_excludes_current_record(db_session: AsyncSession):
    index_repo = TradeNameIndexRepository(db_session)
    lexicon_repo = LexiconRepository(db_session)

    # Seed active name with ID 101
    await index_repo.upsert(
        trade_name_id=101,
        normalized_ar="شركه الرواد",
        normalized_en="al rowad company",
        phonetic_key="RWD|RWD",
        status="active",
    )

    composed = compose("شركة الرواد", "Al Rowad Company", operation_type="edit")
    gates = DeterministicGates(index_repo, lexicon_repo)
    # Exclude ID 101 (editing self)
    signals = await gates.run(composed, exclude_trade_name_id=101)

    assert not any(s.source == "exact_duplicate" for s in signals)


@pytest.mark.asyncio
async def test_gate_released_names_available_f21(db_session: AsyncSession):
    index_repo = TradeNameIndexRepository(db_session)
    lexicon_repo = LexiconRepository(db_session)

    # Seed released/expired name
    await index_repo.upsert(
        trade_name_id=102,
        normalized_ar="شركه الامل",
        normalized_en="al amal company",
        phonetic_key="AML|AML",
        status="released",
    )

    composed = compose("شركة الأمل", "Al Amal Company", operation_type="new")
    gates = DeterministicGates(index_repo, lexicon_repo)
    signals = await gates.run(composed)

    assert not any(s.source == "exact_duplicate" for s in signals)


@pytest.mark.asyncio
async def test_gate_lexicon_hard_block_and_review(db_session: AsyncSession):
    index_repo = TradeNameIndexRepository(db_session)
    lexicon_repo = LexiconRepository(db_session)

    # Seed a block entry and a review entry
    await lexicon_repo.upsert(
        LexiconEntry(
            id=None,
            term="prohibited_word",
            normalized_term="prohibited_word",
            category="prohibited",
            lang="en",
            severity="block",
            approved_by="ADMIN",
        )
    )
    await lexicon_repo.upsert(
        LexiconEntry(
            id=None,
            term="dubai",
            normalized_term="dubai",
            category="location",
            lang="en",
            severity="review",
            approved_by="ADMIN",
        )
    )

    # Test block
    composed_block = compose("اسم عادي", "prohibited_word trading", operation_type="new")
    gates = DeterministicGates(index_repo, lexicon_repo)
    signals_block = await gates.run(composed_block)
    assert any(s.signal_type == SignalType.BLOCKED and s.category == "prohibited" for s in signals_block)

    # Test review
    composed_review = compose("اسم عادي", "dubai trading", operation_type="new")
    signals_review = await gates.run(composed_review)
    assert any(s.signal_type == SignalType.NEEDS_REVIEW and s.category == "location" for s in signals_review)


@pytest.mark.asyncio
async def test_gate_f12_exemption_skips_lexicon_but_runs_exact_dup(db_session: AsyncSession):
    index_repo = TradeNameIndexRepository(db_session)
    lexicon_repo = LexiconRepository(db_session)

    # Seed active name and lexicon entry
    await index_repo.upsert(
        trade_name_id=200,
        normalized_ar="شركه دبي",
        normalized_en="dubai trading",
        phonetic_key="DBY|DBY",
        status="active",
    )
    await lexicon_repo.upsert(
        LexiconEntry(
            id=None,
            term="dubai",
            normalized_term="dubai",
            category="location",
            lang="en",
            severity="review",
            approved_by="ADMIN",
        )
    )

    # Unchanged name where previous name matches current name -> triggers F12 exemption
    composed = compose(
        name_ar="شركة دبي",
        name_en="Dubai Trading",
        operation_type="legal_form_amend",
        previous_name_ar="شركة دبي",
        previous_name_en="Dubai Trading",
    )
    assert composed.skip_word_checks is True

    gates = DeterministicGates(index_repo, lexicon_repo)
    signals = await gates.run(composed, exclude_trade_name_id=999)

    # Lexicon check should be skipped
    assert not any(s.source == "lexicon" for s in signals)
    # Exact duplicate must still run and trigger BLOCKED
    assert any(s.source == "exact_duplicate" and s.signal_type == SignalType.BLOCKED for s in signals)
