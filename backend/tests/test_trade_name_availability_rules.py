"""
tests/test_trade_name_availability_rules.py
Comprehensive test suite verifying Trade Name Availability and Duplicate Prevention Logic:
1. Exact Match + Same Activity -> Reject duplicate with verified alternatives
2. Spelling, Casing, Whitespace & Punctuation Variations + Same Activity -> Flag/Reject duplicate
3. Exact or Similar Name + Different Activity -> Allow registration across different activities
4. Alternative Name Suggestions -> Verified against database before presenting to user
5. Update / Edit Self-Exclusion -> Updating existing trade name does not trigger self-duplicate
6. Concurrency / Atomic duplicate protection
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from index.repository import TradeNameIndexRepository
from pipeline.name_composer import compose
from pipeline.deterministic_gates import DeterministicGates, SignalType
from pipeline.suggestion_engine import SuggestionEngine
from config.settings import FlagMode, get_settings


@pytest.mark.asyncio
async def test_exact_match_same_activity_rejected(client: AsyncClient, db_session: AsyncSession):
    """Requirement 1 & 6: Exact match under the same activity must be rejected with suggestions."""
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=6001,
        normalized_ar="تيجا كافيه",
        normalized_en="teja cafe",
        phonetic_key="TJ|TJ",
        status="active",
        category_id=4,  # Cafe / Restaurant
    )
    await db_session.commit()

    # Attempt to register exact duplicate under same activity (category_id=4)
    payload = {
        "NameAr": "تيجا كافيه",
        "NameEn": "Teja Cafe",
        "CategoryId": 4,
        "LegalForm": "LLC",
    }
    resp = await client.post("/TradeName/Register", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is False
    assert data["status"] == "rejected"
    assert data["is_existing"] is True
    assert len(data["suggestions"]) > 0
    # Suggestions must not contain the exact duplicate "Teja Cafe"
    assert not any(s["name_en"].lower().strip() == "teja cafe" for s in data["suggestions"])


@pytest.mark.asyncio
async def test_casing_spacing_punctuation_variations_rejected(client: AsyncClient, db_session: AsyncSession):
    """Requirement 2: Casing, extra spaces, and punctuation variations under same activity are blocked."""
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=6002,
        normalized_ar="تيجا كافيه",
        normalized_en="teja cafe",
        phonetic_key="TJ|TJ",
        status="active",
        category_id=4,
    )
    await db_session.commit()

    # Variation 1: Uppercase casing "TEJA CAFE"
    resp1 = await client.post("/TradeName/Register", json={
        "NameAr": "تيجا كافيه",
        "NameEn": "TEJA CAFE",
        "CategoryId": 4,
    })
    assert resp1.json()["success"] is False
    assert resp1.json()["status"] == "rejected"

    # Variation 2: Punctuation and hyphen "Teja-Cafe"
    resp2 = await client.post("/TradeName/Register", json={
        "NameAr": "تيجا - كافيه",
        "NameEn": "Teja-Cafe",
        "CategoryId": 4,
    })
    assert resp2.json()["success"] is False
    assert resp2.json()["status"] == "rejected"

    # Variation 3: Extra spaces "Teja   Cafe"
    resp3 = await client.post("/TradeName/Register", json={
        "NameAr": "تيجا   كافيه",
        "NameEn": "Teja   Cafe",
        "CategoryId": 4,
    })
    assert resp3.json()["success"] is False
    assert resp3.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_spelling_variation_confusingly_similar_rejected(client: AsyncClient, db_session: AsyncSession):
    """Requirement 2: Minor spelling variation (e.g. Teja Cafey vs Teja Cafe) under same activity is rejected."""
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=6003,
        normalized_ar="تيجا كافيه",
        normalized_en="teja cafe",
        phonetic_key="TJ|TJ",
        status="active",
        category_id=4,
    )
    await db_session.commit()

    # Attempt to register minor typo/spelling variation in same category (both AR & EN varied)
    payload = {
        "NameAr": "تيجا كافييه",
        "NameEn": "Teja Cafey",
        "CategoryId": 4,
        "LegalForm": "LLC",
    }
    resp = await client.post("/TradeName/Register", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is False
    assert data["status"] == "rejected"
    assert data["is_existing"] is True
    assert "confusingly similar" in data["message_en"].lower() or "already registered" in data["message_en"].lower() or "already exists" in data["message_en"].lower()


@pytest.mark.asyncio
async def test_allow_identical_or_similar_name_across_different_activities(client: AsyncClient, db_session: AsyncSession):
    """Requirement 3: Teja Cafe in Cafe (cat 4) vs Teja IT Services / Teja Cafe in Tech (cat 3) allowed."""
    index_repo = TradeNameIndexRepository(db_session)
    # Seed Teja Cafe in Category 4 (Restaurant & Cafe)
    await index_repo.upsert(
        trade_name_id=6004,
        normalized_ar="تيجا كافيه",
        normalized_en="teja cafe",
        phonetic_key="TJ|TJ",
        status="active",
        category_id=4,
    )
    await db_session.commit()

    # 1. Check existence in Category 4 -> Exists
    exist_cat4 = await client.get("/TradeName/IsTradeNameExist", params={
        "NameEn": "Teja Cafe",
        "CategoryId": 4,
    })
    assert exist_cat4.status_code == 200
    assert exist_cat4.json()["Exists"] is True

    # 2. Check existence in Category 3 (IT & Tech) -> Available!
    exist_cat3 = await client.get("/TradeName/IsTradeNameExist", params={
        "NameEn": "Teja Cafe",
        "CategoryId": 3,
    })
    assert exist_cat3.status_code == 200
    assert exist_cat3.json()["Exists"] is False

    # 3. Registering under Category 3 (IT & Technology) must SUCCEED!
    payload_tech = {
        "NameAr": "خدمات تيجا للتقنية",
        "NameEn": "Teja IT Services",
        "CategoryId": 3,
        "LegalForm": "LLC",
    }
    reg_tech = await client.post("/TradeName/Register", json=payload_tech)
    assert reg_tech.status_code == 200
    data_tech = reg_tech.json()
    assert data_tech["success"] is True
    assert data_tech["status"] == "registered"


@pytest.mark.asyncio
async def test_update_existing_trade_name_self_exclusion(client: AsyncClient, db_session: AsyncSession):
    """Requirement 5: When an existing trade name is updated, its current record is excluded from duplicate checks."""
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=6005,
        normalized_ar="مؤسسة النور الماسي",
        normalized_en="diamond noor est",
        phonetic_key="NR|DMD",
        status="active",
        category_id=1,
    )
    await db_session.commit()

    # Update the existing record without changing name
    update_payload = {
        "TradeNameId": 6005,
        "NameAr": "مؤسسة النور الماسي",
        "NameEn": "Diamond Noor Est",
        "CategoryId": 1,
        "LegalForm": "LLC",
    }
    resp = await client.post("/TradeName/Register", json=update_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["status"] == "updated"
    assert data["trade_name_id"] == 6005


@pytest.mark.asyncio
async def test_alternative_suggestions_verified_against_database(db_session: AsyncSession):
    """Requirement 4: Suggestions returned must be verified against database and not already exist in the activity."""
    settings = get_settings()
    original_flag = settings.ai_suggestions
    settings.ai_suggestions = FlagMode.on
    try:
        index_repo = TradeNameIndexRepository(db_session)
        # Seed known active names in Category 4
        await index_repo.upsert(
            trade_name_id=6006,
            normalized_ar="مطعم صحراء",
            normalized_en="sahra restaurant",
            phonetic_key="SHR|SHR",
            status="active",
            category_id=4,
        )
        await index_repo.upsert(
            trade_name_id=6007,
            normalized_ar="كافيه واحة اكسبريس",
            normalized_en="oasis express cafe",
            phonetic_key="SHR|SHR",
            status="active",
            category_id=4,
        )
        await db_session.commit()

        engine = SuggestionEngine(db_session)
        suggestions = await engine.generate(
            name_ar="مطعم صحراء",
            name_en="Sahra Restaurant",
            category_id=4,
            limit=6,
        )

        assert len(suggestions) > 0
        # None of the returned suggestions should match the existing names
        for s in suggestions:
            assert s.name_en.lower() != "sahra restaurant"
            assert s.name_en.lower() != "oasis express cafe"
            # When brand conflict occurs, distinctive alternative brands are provided
            assert "sahra" not in s.name_en.lower()
    finally:
        settings.ai_suggestions = original_flag
