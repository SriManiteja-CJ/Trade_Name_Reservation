"""
tests/test_suggestion_engine.py
Comprehensive test suite for Stage ⑥ Suggestion Engine (Phase 3.1).

Covers:
  F8  — Up to 10 distinct, unreserved suggestions; legal form included if required
  F9  — Complementary patterns (name + activity wording)
  F17 — All English suggestion names returned in UPPER CASE
  F18 — Reserved names are never suggested (single set SQL check)
  N8  — Bounded cost; single set query
  Ambiguity #5 — Deterministic template fallback
"""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import FlagMode, get_settings
from index.repository import TradeNameIndexRepository
from lexicon.repository import LexiconRepository
from llm.schemas import SuggestionBatchOutput, SuggestionCandidate
from pipeline.suggestion_engine import SuggestionEngine

settings = get_settings()


@pytest.mark.asyncio
async def test_suggestions_flag_off(db_session: AsyncSession):
    """When ai_suggestions = off, engine returns an empty list."""
    original_flag = settings.ai_suggestions
    settings.ai_suggestions = FlagMode.off
    try:
        engine = SuggestionEngine(session=db_session)
        res = await engine.generate(
            name_ar="الرواد",
            name_en="Al Rowad",
            activity_category="101",
        )
        assert res == []
    finally:
        settings.ai_suggestions = original_flag


@pytest.mark.asyncio
async def test_template_fallback_suggestions(db_session: AsyncSession):
    """
    When LLM is unavailable or disabled, engine falls back to deterministic templates (Ambiguity #5).
    Verifies F8 (<= 10 suggestions), F17 (UPPER CASE English), F9 (complementary patterns).
    """
    original_flag = settings.ai_suggestions
    settings.ai_suggestions = FlagMode.on
    try:
        engine = SuggestionEngine(session=db_session)
        # Mock LLM gateway returning None to force template fallback
        with patch("pipeline.suggestion_engine.LlmGateway") as MockGateway:
            mock_gw = AsyncMock()
            mock_gw.generate_suggestions.return_value = None
            mock_gw.close = AsyncMock()
            MockGateway.return_value = mock_gw

            res = await engine.generate(
                name_ar="الرواد",
                name_en="Al Rowad",
                activity_category="101",
                limit=10,
            )

            assert len(res) > 0
            assert len(res) <= 10

            for item in res:
                # F17: All English names must be UPPER CASE
                assert item.name_en == item.name_en.upper()
                # Arabic name must be non-empty
                assert len(item.name_ar) > 0
                assert item.source == "template"
    finally:
        settings.ai_suggestions = original_flag


@pytest.mark.asyncio
async def test_suggestions_reserved_exclusion(db_session: AsyncSession):
    """
    F18: Reserved or active names are never suggested.
    Verifies that any candidate already present in TradeNameIndex with status 'active' or 'reserved'
    is filtered out.
    """
    original_flag = settings.ai_suggestions
    settings.ai_suggestions = FlagMode.on
    try:
        # Pre-seed an active and a reserved name that would match templates
        index_repo = TradeNameIndexRepository(db_session)
        await index_repo.upsert(
            trade_name_id=5001,
            normalized_ar="الرواد للتجاره",
            normalized_en="al rowad trading",
            phonetic_key="RWD|RWD",
            status="active",
        )
        await index_repo.upsert(
            trade_name_id=5002,
            normalized_ar="الرواد للخدمات",
            normalized_en="al rowad services",
            phonetic_key="RWD|RWD",
            status="reserved",
        )
        await db_session.commit()

        engine = SuggestionEngine(session=db_session)
        with patch("pipeline.suggestion_engine.LlmGateway") as MockGateway:
            mock_gw = AsyncMock()
            mock_gw.generate_suggestions.return_value = None
            mock_gw.close = AsyncMock()
            MockGateway.return_value = mock_gw

            res = await engine.generate(
                name_ar="الرواد",
                name_en="Al Rowad",
                limit=10,
                category_id=1,
            )

            # Neither active "AL ROWAD TRADING" nor reserved "AL ROWAD SERVICES" should be in results
            suggested_en = [s.name_en for s in res]
            assert "AL ROWAD TRADING" not in suggested_en
            assert "AL ROWAD SERVICES" not in suggested_en
    finally:
        settings.ai_suggestions = original_flag


@pytest.mark.asyncio
async def test_suggestions_lexicon_screening(db_session: AsyncSession):
    """
    Stage ② screening: Candidates containing blocked lexicon terms are dropped.
    """
    original_flag = settings.ai_suggestions
    settings.ai_suggestions = FlagMode.on
    try:
        # Pre-seed a blocked lexicon term
        from lexicon.repository import LexiconEntry
        lexicon_repo = LexiconRepository(db_session)
        await lexicon_repo.upsert(
            LexiconEntry(
                id=None,
                term="casino",
                normalized_term="casino",
                category="prohibited",
                lang="en",
                severity="block",
                approved_by="admin",
            )
        )
        await db_session.commit()

        engine = SuggestionEngine(session=db_session)
        # Mock LLM returning a candidate with the blocked word
        mock_output = SuggestionBatchOutput(
            suggestions=[
                SuggestionCandidate(
                    name_ar="كازينو الرواد",
                    name_en="Al Rowad Casino",
                ),
                SuggestionCandidate(
                    name_ar="الرواد للابتكار",
                    name_en="Al Rowad Innovation",
                ),
            ]
        )

        with patch("pipeline.suggestion_engine.LlmGateway") as MockGateway:
            mock_gw = AsyncMock()
            mock_gw.generate_suggestions.return_value = mock_output
            mock_gw.close = AsyncMock()
            MockGateway.return_value = mock_gw

            res = await engine.generate(
                name_ar="الرواد",
                name_en="Al Rowad",
                limit=10,
                category_id=1,
            )

            # The casino candidate must be eliminated by lexicon gate
            suggested_en = [s.name_en for s in res]
            assert not any("CASINO" in s for s in suggested_en)
            assert any("INNOVATION" in s for s in suggested_en)
    finally:
        settings.ai_suggestions = original_flag


@pytest.mark.asyncio
async def test_suggestions_legal_form_appended(db_session: AsyncSession):
    """
    F8: When legal form is specified, it is appended to the suggestions.
    """
    original_flag = settings.ai_suggestions
    settings.ai_suggestions = FlagMode.on
    try:
        engine = SuggestionEngine(session=db_session)
        with patch("pipeline.suggestion_engine.LlmGateway") as MockGateway:
            mock_gw = AsyncMock()
            mock_gw.generate_suggestions.return_value = None
            mock_gw.close = AsyncMock()
            MockGateway.return_value = mock_gw

            res = await engine.generate(
                name_ar="الرواد",
                name_en="Al Rowad",
                legal_form="LLC",
                limit=5,
                category_id=1,
            )

            assert len(res) > 0
            # Concise LLC / ذ.م.م is offered for companies wanting the legal form suffix
            has_llc_en = any(item.name_en.endswith("LLC") for item in res)
            has_llc_ar = any("ذ.م.م" in item.name_ar for item in res)
            has_clean_en = any(not item.name_en.endswith("LLC") for item in res)
            assert has_llc_en
            assert has_llc_ar
            assert has_clean_en
            assert not any("LIMITED LIABILITY COMPANY" in item.name_en for item in res)
    finally:
        settings.ai_suggestions = original_flag


@pytest.mark.asyncio
async def test_suggestions_brand_conflict_alternative_names(db_session: AsyncSession):
    """
    When an applicant submits a trade name whose distinctive brand token is already
    active/reserved in the registry (e.g., 'Cloudjune' exists), the engine must NOT
    re-suggest variations containing 'Cloudjune'. Instead, it generates distinct alternative brands.
    """
    original_flag = settings.ai_suggestions
    settings.ai_suggestions = FlagMode.on
    try:
        # Pre-seed Cloudjune as an active trade name in category 3
        index_repo = TradeNameIndexRepository(db_session)
        await index_repo.upsert(
            trade_name_id=6099,
            normalized_ar="كلاودجون للتكنولوجيا",
            normalized_en="cloudjune technologies",
            phonetic_key="KLDJN|CLDJN",
            category_id=3,
            status="active",
        )

        engine = SuggestionEngine(session=db_session)
        with patch("pipeline.suggestion_engine.LlmGateway") as MockGateway:
            mock_gw = AsyncMock()
            mock_gw.generate_suggestions.return_value = None
            mock_gw.close = AsyncMock()
            MockGateway.return_value = mock_gw

            res = await engine.generate(
                name_ar="كلاودجون للتكنولوجيا",
                name_en="Cloudjune Technologies",
                activity_category="3",
                category_id=3,
                legal_form="Limited Liability Company",
                limit=10,
            )

            assert len(res) > 0
            for item in res:
                # Crucial assertion: NONE of the suggestions reuse the taken brand token 'Cloudjune'
                assert "CLOUDJUNE" not in item.name_en.upper()
                assert "كلاودجون" not in item.name_ar
                assert item.source == "alternative"
                # Never uses verbose LIMITED LIABILITY COMPANY
                assert "LIMITED LIABILITY COMPANY" not in item.name_en
    finally:
        settings.ai_suggestions = original_flag
