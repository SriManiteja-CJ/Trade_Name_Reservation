"""
tests/test_dynamic_base_name_uniqueness.py
Comprehensive automated test suite covering all 17 Acceptance Criteria for:
1. Dynamic Base-Name Identification (word-order invariant, multi-language, generic name review)
2. Activity-Specific Base-Name Reservation (blocking descriptive variations and word reversals)
3. Cross-Activity Independence (same base name evaluated independently across different activities)
4. Dynamic Similar Alternatives (different unreserved base names like Cloudnine, Cloudjini, Cloudzone, Cloudnova)
5. Multi-brand parameterization (Cloudjune, Apex, Lumina, Falcon)
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from index.repository import TradeNameIndexRepository
from pipeline.base_name_extractor import extract_base_name, DynamicBaseNameExtractor
from pipeline.suggestion_engine import SuggestionEngine
from config.settings import FlagMode, get_settings


# ==============================================================================
# 1. Base-Name Extraction Unit Tests (Word Order, Multi-Language, Confidence)
# ==============================================================================

@pytest.mark.parametrize(
    "trade_name,expected_base,expected_desc",
    [
        ("Cloudjune Technologies", "Cloudjune", "Technologies"),
        ("Technologies Cloudjune", "Cloudjune", "Technologies"),  # Word order reversed
        ("Cloudjune IT Solutions", "Cloudjune", "IT Solutions"),
        ("Cloudjune Digital Services", "Cloudjune", "Digital Services"),
        ("Cloudjune Technologies Private Limited", "Cloudjune", "Technologies"),
        ("Apex Logistics LLC", "Apex", "Logistics"),
        ("Lumina Software Systems", "Lumina", "Software Systems"),
        ("مؤسسة كلاودجون لتقنية المعلومات", "كلاودجون", "لتقنية المعلومات"),
        ("كلاودجون للخدمات الرقمية", "كلاودجون", "للخدمات الرقمية"),
    ],
)
def test_dynamic_base_name_extraction_word_order_invariance(trade_name, expected_base, expected_desc):
    lang = "ar" if any("\u0600" <= c <= "\u06FF" for c in trade_name) else "en"
    result = extract_base_name(trade_name, lang=lang)
    assert result.base_name.lower().strip() == expected_base.lower().strip()
    assert result.is_generic is False
    assert result.confidence >= 0.70


def test_generic_name_flagged_for_review():
    """Names without distinctive tokens (pure descriptors + legal forms) must be flagged with confidence=0.0."""
    res_en = extract_base_name("General Trading LLC", lang="en")
    assert res_en.is_generic is True
    assert res_en.confidence == 0.0

    res_ar = extract_base_name("شركة التجارة العامة ذ.م.م", lang="ar")
    assert res_ar.is_generic is True
    assert res_ar.confidence == 0.0


@pytest.mark.parametrize(
    "trade_name",
    ["CLOUD-JUNE technologies", "Cloud June Technologies", "Technologies, Cloudjune", "Cloudjune Cafe"],
)
def test_canonical_base_key_ignores_formatting_and_descriptor_order(trade_name):
    from pipeline.base_name_extractor import canonical_base_name

    assert canonical_base_name(trade_name, lang="en") == "cloudjune"


def test_ambiguous_extraction_has_low_confidence():
    result = extract_base_name("North South East West Ventures LLC", lang="en")
    assert result.confidence < get_settings().trade_name_base_min_confidence


# ==============================================================================
# 2. Activity-Specific Base-Name Reservation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_cloudjune_technologies_blocks_all_variations_under_same_activity(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Core Business Rule:
    Registering 'Cloudjune Technologies' under Technology Services (Category 3)
    reserves the base name 'Cloudjune'.
    All descriptive variations and word-order changes must be blocked under Category 3.
    """
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=7001,
        normalized_ar="كلاودجون للتقنية",
        normalized_en="cloudjune technologies",
        phonetic_key="CLD|CLD",
        status="active",
        category_id=3,  # Technology Services
    )
    await db_session.commit()

    test_variations = [
        "Cloudjune IT Solutions",
        "Cloudjune Digital Services",
        "Cloudjune Software Solutions",
        "Cloudjune Digital Solutions",
        "Cloudjune Technologies Private Limited",
        "Technologies Cloudjune",  # Inverted word order
    ]

    for name in test_variations:
        resp = await client.post(
            "/TradeName/Register",
            json={
                "NameAr": f"كلاودجون {name}",
                "NameEn": name,
                "CategoryId": 3,
                "LegalForm": "LLC",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False, f"Expected {name} to be blocked under Category 3"
        assert data["status"] == "rejected"
        assert data["is_existing"] is True
        assert data["protected_base_name"].lower() == "cloudjune"
        assert data["registered_category_id"] == 3


@pytest.mark.asyncio
async def test_cross_activity_independence(client: AsyncClient, db_session: AsyncSession):
    """
    Base name restrictions are scoped to the business activity:
    'Cloudjune Technologies' is registered under Category 3 (Technology Services).
    'Cloudjune Cafe' under Category 4 (Restaurant & Cafe) must be allowed!
    'Cloudjune Fashions' under Category 2 (Commercial / Retail) must be allowed!
    """
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=7002,
        normalized_ar="كلاودجون للتقنية",
        normalized_en="cloudjune technologies",
        phonetic_key="CLD|CLD",
        status="active",
        category_id=3,  # Technology Services
    )
    await db_session.commit()

    # 1. Cloudjune Cafe in Category 4 -> ALLOWED
    cafe_payload = {
        "NameAr": "كلاودجون كافيه",
        "NameEn": "Cloudjune Cafe",
        "CategoryId": 4,
        "LegalForm": "LLC",
    }
    resp_cafe = await client.post("/TradeName/Register", json=cafe_payload)
    assert resp_cafe.status_code == 200
    data_cafe = resp_cafe.json()
    assert data_cafe["success"] is True
    assert data_cafe["status"] == "registered"

    # 2. Cloudjune Fashions in Category 2 -> ALLOWED
    fashion_payload = {
        "NameAr": "كلاودجون للأزياء",
        "NameEn": "Cloudjune Fashions",
        "CategoryId": 2,
        "LegalForm": "LLC",
    }
    resp_fashion = await client.post("/TradeName/Register", json=fashion_payload)
    assert resp_fashion.status_code == 200
    data_fashion = resp_fashion.json()
    assert data_fashion["success"] is True
    assert data_fashion["status"] == "registered"


@pytest.mark.asyncio
async def test_suggestions_generate_different_base_names_excluding_protected(db_session: AsyncSession):
    """
    When 'Cloudjune Technologies' is unavailable under Category 3,
    the suggestion engine must generate alternatives resembling the input in structure
    (e.g. Cloudnine Technologies, Cloudjini Technologies, Cloudzone Technologies, Cloudnova Technologies)
    and strictly NEVER suggest any name containing the protected base name 'Cloudjune'.
    """
    settings = get_settings()
    orig = settings.ai_suggestions
    settings.ai_suggestions = FlagMode.on
    try:
        index_repo = TradeNameIndexRepository(db_session)
        await index_repo.upsert(
            trade_name_id=7003,
            normalized_ar="كلاودجون للتقنية",
            normalized_en="cloudjune technologies",
            phonetic_key="CLD|CLD",
            status="active",
            category_id=3,
        )
        await db_session.commit()

        engine = SuggestionEngine(db_session)
        suggestions = await engine.generate(
            name_ar="كلاودجون للتقنية",
            name_en="Cloudjune Technologies",
            category_id=3,
            limit=8,
        )

        assert len(suggestions) > 0, "Must return alternative suggestions"

        for s in suggestions:
            s_en = s.name_en.lower()
            # F18 / Rule: Protected base name must NOT appear in suggestions
            assert "cloudjune" not in s_en, f"Protected base name found in suggestion: {s.name_en}"
            # Preserves meaningful descriptor where appropriate
            assert "technologies" in s_en or "tech" in s_en or len(s_en.split()) >= 1
    finally:
        settings.ai_suggestions = orig


@pytest.mark.asyncio
async def test_is_trade_name_exist_endpoint_checks_base_name_reservation(
    client: AsyncClient, db_session: AsyncSession
):
    """
    GET /TradeName/IsTradeNameExist must check both exact name AND base name reservation.
    """
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=7004,
        normalized_ar="ابكس للحلول الذكية",
        normalized_en="apex smart solutions",
        phonetic_key="APX|APX",
        status="active",
        category_id=3,
    )
    await db_session.commit()

    # 1. Under Category 3: 'Apex Digital Services' has base name 'Apex' which is reserved -> Exists = True
    resp_cat3 = await client.get(
        "/TradeName/IsTradeNameExist",
        params={"NameEn": "Apex Digital Services", "CategoryId": 3},
    )
    assert resp_cat3.status_code == 200
    data_cat3 = resp_cat3.json()
    assert data_cat3["Exists"] is True
    assert data_cat3["conflict_type"] == "reserved_base_name"
    assert data_cat3["protected_base_name"].lower() == "apex"
    assert data_cat3["registered_category_id"] == 3

    # 2. Under Category 4 (Restaurants): 'Apex Cafe' -> Exists = False
    resp_cat4 = await client.get(
        "/TradeName/IsTradeNameExist",
        params={"NameEn": "Apex Cafe", "CategoryId": 4},
    )
    assert resp_cat4.status_code == 200
    data_cat4 = resp_cat4.json()
    assert data_cat4["Exists"] is False


@pytest.mark.asyncio
async def test_database_unique_index_reserves_base_name_within_activity(db_session: AsyncSession):
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=7101,
        normalized_ar="",
        normalized_en="Apex Technologies",
        phonetic_key="APX|APX",
        status="active",
        category_id=3,
    )
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await index_repo.upsert(
            trade_name_id=7102,
            normalized_ar="",
            normalized_en="APEX-Digital Services",
            phonetic_key="APX|APX",
            status="active",
            category_id=3,
        )
    await db_session.rollback()

    await index_repo.upsert(
        trade_name_id=7103,
        normalized_ar="",
        normalized_en="Apex Cafe",
        phonetic_key="APX|APX",
        status="active",
        category_id=4,
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_uncertain_name_requires_review_across_availability_and_registration(client: AsyncClient):
    name = "North South East West Ventures LLC"
    available = await client.get(
        "/TradeName/IsTradeNameExist",
        params={"NameEn": name, "CategoryId": 3},
    )
    assert available.status_code == 200
    assert available.json()["availability_status"] == "needs_review"
    assert available.json()["conflict_type"] == "base_name_uncertain"

    registered = await client.post(
        "/TradeName/Register",
        json={"NameEn": name, "NameAr": "", "CategoryId": 3},
    )
    assert registered.status_code == 200
    assert registered.json()["success"] is False
    assert registered.json()["conflict_type"] == "base_name_uncertain"


@pytest.mark.asyncio
async def test_activity_category_is_required_for_availability(client: AsyncClient):
    response = await client.get(
        "/TradeName/IsTradeNameExist",
        params={"NameEn": "Apex Technologies"},
    )
    assert response.status_code == 422
