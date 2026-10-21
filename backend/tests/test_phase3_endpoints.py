"""
tests/test_phase3_endpoints.py
Integration tests for Phase 3 endpoints:
  - Phase 3.1: Suggestions in ValidateWithSuggestion (F8, F9, F17, F18)
  - Phase 3.2: CheckTransliteration (F7)
  - Phase 3.3: SuggestCategory (E6)
  - Phase 3.4: Hybrid Search across languages (F19, F22, E8)
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import FlagMode, get_settings
from index.repository import TradeNameIndexRepository
from llm.schemas import CategorySuggestionOutput, TransliterationCheckOutput

settings = get_settings()


# ---------------------------------------------------------------------------
# Phase 3.2: CheckTransliteration Endpoint (F7)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_check_transliteration_deterministic(client: AsyncClient):
    """
    POST /TradeName/CheckTransliteration: Deterministic CAMeL/phonetic fallback.
    Consistent pair: Al Noor / النور -> consistent=True
    Inconsistent pair: Falcon / النور -> consistent=False
    """
    original_flag = settings.ai_analyzer
    settings.ai_analyzer = FlagMode.off
    try:
        # 1. Matching transliteration
        resp_match = await client.post(
            "/TradeName/CheckTransliteration",
            json={"NameAr": "النور", "NameEn": "Al Noor"},
        )
        assert resp_match.status_code == 200
        data_match = resp_match.json()
        assert data_match["consistent"] is True
        assert data_match["confidence"] >= 0.8
        assert data_match["expected_en"] == "AL NOOR"
        assert data_match["expected_ar"] == "النور"

        # 2. Inconsistent transliteration
        resp_mismatch = await client.post(
            "/TradeName/CheckTransliteration",
            json={"NameAr": "البركة", "NameEn": "Falcon"},
        )
        assert resp_mismatch.status_code == 200
        data_mismatch = resp_mismatch.json()
        assert data_mismatch["consistent"] is False
        assert data_mismatch["confidence"] < 0.6
    finally:
        settings.ai_analyzer = original_flag


@pytest.mark.asyncio
async def test_check_transliteration_llm_mode(client: AsyncClient):
    """
    POST /TradeName/CheckTransliteration: LLM-backed evaluation when ai_analyzer=on.
    """
    original_flag = settings.ai_analyzer
    settings.ai_analyzer = FlagMode.on
    try:
        mock_output = TransliterationCheckOutput(
            consistent=True,
            confidence=0.98,
            expected_en="AL ROWAD",
            expected_ar="الرواد",
            reason_en="Accurate transliteration.",
            reason_ar="مطابقة صوتية دقيقة.",
        )
        with patch("api.routes.trade_name.LlmGateway") as MockGateway:
            mock_gw = AsyncMock()
            mock_gw.check_transliteration.return_value = mock_output
            mock_gw.close = AsyncMock()
            MockGateway.return_value = mock_gw

            resp = await client.post(
                "/TradeName/CheckTransliteration",
                json={"NameAr": "الرواد", "NameEn": "Al Rowad"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["consistent"] is True
            assert data["confidence"] == 0.98
            assert data["expected_en"] == "AL ROWAD"
    finally:
        settings.ai_analyzer = original_flag


# ---------------------------------------------------------------------------
# Phase 3.3: SuggestCategory Endpoint (E6)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_suggest_category_deterministic(client: AsyncClient):
    """
    POST /TradeName/SuggestCategory: Deterministic keyword classification fallback.
    """
    original_flag = settings.ai_analyzer
    settings.ai_analyzer = FlagMode.off
    try:
        # Tech keywords
        resp_tech = await client.post(
            "/TradeName/SuggestCategory",
            json={"NameAr": "شركة الحلول البرمجية", "NameEn": "Tech Solutions Software", "ActivityType": "Software development"},
        )
        assert resp_tech.status_code == 200
        assert resp_tech.json()["suggested_category_code"] == "TECH_003"
        assert "tech" in resp_tech.json()["reason_en"].lower() or "technology" in resp_tech.json()["reason_en"].lower() or "aligned" in resp_tech.json()["reason_en"].lower()

        # Restaurant keywords
        resp_rest = await client.post(
            "/TradeName/SuggestCategory",
            json={"NameAr": "مطعم ومقهى السعادة", "NameEn": "Happiness Restaurant & Cafe", "ActivityType": "Restaurant"},
        )
        assert resp_rest.status_code == 200
        assert resp_rest.json()["suggested_category_code"] == "REST_004"

        # Manufacturing keywords
        resp_cont = await client.post(
            "/TradeName/SuggestCategory",
            json={"NameAr": "مصنع الأفق للحديد", "NameEn": "Al Ofoq Iron Manufacturing", "ActivityType": "Manufacturing"},
        )
        assert resp_cont.status_code == 200
        assert resp_cont.json()["suggested_category_code"] == "INDU_007"

        # Consultancy keywords
        resp_serv = await client.post(
            "/TradeName/SuggestCategory",
            json={"NameAr": "رواد للاستشارات الإدارية", "NameEn": "Rowad Management Consulting", "ActivityType": "Management consultancy"},
        )
        assert resp_serv.status_code == 200
        assert resp_serv.json()["suggested_category_code"] == "SERV_002"
    finally:
        settings.ai_analyzer = original_flag


@pytest.mark.asyncio
async def test_suggest_category_llm_mode(client: AsyncClient):
    """
    POST /TradeName/SuggestCategory: LLM-backed suggestion when ai_analyzer=on.
    """
    original_flag = settings.ai_analyzer
    settings.ai_analyzer = FlagMode.on
    try:
        mock_output = {
            "recommended_category_code": "SERV_002",
            "confidence": 0.92,
            "reason_en": "Specialized in real estate asset management.",
            "reason_ar": "متخصص في إدارة الأصول العقارية.",
            "recommended_activity_type": "Real estate management",
        }
        with patch("api.routes.trade_name.LlmGateway") as MockGateway:
            mock_gw = AsyncMock()
            mock_gw.suggest_category.return_value = mock_output
            mock_gw.close = AsyncMock()
            MockGateway.return_value = mock_gw

            resp = await client.post(
                "/TradeName/SuggestCategory",
                json={"NameAr": "إعمار العقارية", "NameEn": "Emaar Properties"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["suggested_category_code"] == "SERV_002"
            assert data["reason_en"] == "Specialized in real estate asset management."
    finally:
        settings.ai_analyzer = original_flag


# ---------------------------------------------------------------------------
# Phase 3.1: Suggestions integrated in ValidateWithSuggestion
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_validate_with_suggestion_returns_suggestions(client: AsyncClient):
    """
    POST /TradeName/ValidateWithSuggestion returns suggestions when ai_suggestions=on.
    Verifies F8 (<= 10 suggestions) and F17 (English uppercase).
    """
    original_flag = settings.ai_suggestions
    settings.ai_suggestions = FlagMode.on
    try:
        payload = {
            "NameAr": "شركة الابتكار للحلول",
            "NameEn": "Innovation Solutions LLC",
            "RequestId": "UAQ-TEST-3001",
            "OperationType": "new",
            "LegalForm": "LLC",
            "ActivityCategoryId": 3,
        }
        resp = await client.post("/TradeName/ValidateWithSuggestion", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) > 0
        assert len(data["suggestions"]) <= 10

        for item in data["suggestions"]:
            assert "name_ar" in item
            assert "name_en" in item
            # F17: All English suggestion names in UPPER CASE
            assert item["name_en"] == item["name_en"].upper()
    finally:
        settings.ai_suggestions = original_flag


# ---------------------------------------------------------------------------
# Phase 3.4: Hybrid Search Cross-Language (F19, F22, E8)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hybrid_search_cross_language(client: AsyncClient, db_session: AsyncSession):
    """
    GET /TradeName/Search: Tests cross-language retrieval using hybrid retriever (F22, E8).
    """
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=7001,
        normalized_ar="نور الشمس للخدمات",
        normalized_en="nour al shams services",
        phonetic_key="NWR0SMS|NWR0SMS",
        status="active",
    )
    await db_session.commit()

    # Search with phonetic/English keyword "Noor" -> should find the entry
    resp_en = await client.get("/TradeName/Search", params={"Keyword": "Noor Shams", "Limit": 5})
    assert resp_en.status_code == 200
    data_en = resp_en.json()
    assert data_en["Total"] >= 1
    assert data_en["Results"][0]["registry_id"] == 7001

    # Search with Arabic keyword "نور"
    resp_ar = await client.get("/TradeName/Search", params={"Keyword": "نور الشمس", "Limit": 5})
    assert resp_ar.status_code == 200
    data_ar = resp_ar.json()
    assert data_ar["Total"] >= 1
    assert data_ar["Results"][0]["registry_id"] == 7001
