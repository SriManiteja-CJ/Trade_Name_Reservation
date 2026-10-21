"""
tests/test_lexicon_repository.py
Integration tests for LexiconRepository (lexicon/repository.py).

Spec references:
  F4 — Word checks: prohibited, profanity, unfriendly, special, divine_name, location, family_name
  E7 — Admin proposals and approvals
  Phase 1.4 — Lexicon repository CRUD & fuzzy variant lookup
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lexicon.repository import LexiconEntry, LexiconRepository


@pytest.mark.asyncio
async def test_lexicon_upsert_and_find_exact(db_session: AsyncSession):
    repo = LexiconRepository(db_session)
    entry = LexiconEntry(
        id=None,
        term="مقامرة",
        normalized_term="مقامره",
        category="prohibited",
        lang="ar",
        severity="block",
        variants=["قمار", "ميسر"],
        approved_by="DED_ADMIN_1",
    )
    upserted = await repo.upsert(entry)
    assert upserted.id is not None
    assert upserted.term == "مقامرة"

    # Find exact
    matches = await repo.find_matches("مقامره", lang="ar")
    assert len(matches) == 1
    assert matches[0].term == "مقامرة"


@pytest.mark.asyncio
async def test_lexicon_fuzzy_variant_match(db_session: AsyncSession):
    repo = LexiconRepository(db_session)
    entry = LexiconEntry(
        id=None,
        term="casino",
        normalized_term="casino",
        category="prohibited",
        lang="en",
        severity="block",
        variants=["kassino", "cazino"],
        approved_by="DED_ADMIN_1",
    )
    await repo.upsert(entry)

    # Search with variant "kassino"
    matches = await repo.find_matches("kassino", lang="en")
    assert len(matches) == 1
    assert matches[0].term == "casino"


@pytest.mark.asyncio
async def test_lexicon_pending_proposals(db_session: AsyncSession):
    repo = LexiconRepository(db_session)
    # Entry without approval (pending)
    pending_entry = LexiconEntry(
        id=None,
        term="unverified_term",
        normalized_term="unverified_term",
        category="special",
        lang="en",
        severity="review",
        approved_by=None,
    )
    await repo.upsert(pending_entry)

    pending_list = await repo.list_pending_proposals()
    assert len(pending_list) == 1
    assert pending_list[0].term == "unverified_term"
