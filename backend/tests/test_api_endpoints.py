"""
tests/test_api_endpoints.py
Integration tests for FastAPI endpoints (api/routes/trade_name.py & admin.py).

Spec references:
  §5.2 — API contracts for TradeName endpoints
  N9   — Backward-compatible legacy response fields
  F1, F2, F4, F10, F11, F12, F13, F14, F19, F21
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from index.repository import TradeNameIndexRepository
from lexicon.repository import LexiconEntry, LexiconRepository


@pytest.mark.asyncio
async def test_health_and_readiness_endpoints(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "feature_flags" in data
    assert data["feature_flags"]["ai_analyzer"] in ("off", "shadow", "on")

    resp_ready = await client.get("/ready")
    assert resp_ready.status_code == 200
    assert resp_ready.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_validate_clean_name_ok(client: AsyncClient, db_session: AsyncSession):
    from config.settings import FlagMode, get_settings
    settings = get_settings()
    orig_flag = settings.ai_analyzer
    settings.ai_analyzer = FlagMode.off
    try:
        payload = {
            "NameAr": "شركة الإبداع للتقنية",
            "NameEn": "Creativity Tech LLC",
            "RequestId": "REQ-001",
            "OperationType": "new",
            "LegalForm": "LLC",
            "ActivityCategoryId": 3,
        }
        resp = await client.post("/TradeName/ValidateWithSuggestion", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        # Legacy fields (N9)
        assert data["Prohibted"] is False
        assert data["Profanity"] is False
        assert data["Unfriendly"] is False
        assert data["Special"] is False
        assert data["AllahNames"] is False
        assert data["LocationNames"] is False
        assert data["FamilyNames"] is False
        assert data["Similarity"] == 0.0

        # Additive fields
        assert data["decision"] == "OK"
        assert len(data["reasons"]) == 0
    finally:
        settings.ai_analyzer = orig_flag


@pytest.mark.asyncio
async def test_validate_exact_duplicate_blocked(client: AsyncClient, db_session: AsyncSession):
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=1001,
        normalized_ar="شركه الابداع للتقنيه",
        normalized_en="creativity tech llc",
        phonetic_key="BD|CRT",
        status="active",
    )
    await db_session.commit()

    payload = {
        "NameAr": "شركة الإبداع للتقنية",
        "NameEn": "Creativity Tech LLC",
        "RequestId": "REQ-002",
        "OperationType": "new",
    }
    resp = await client.post("/TradeName/ValidateWithSuggestion", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["decision"] == "BLOCKED"
    assert data["is_existing"] is True
    assert any(r["category"] == "exact_duplicate" for r in data["reasons"])


@pytest.mark.asyncio
async def test_validate_lexicon_hard_block(client: AsyncClient, db_session: AsyncSession):
    lexicon_repo = LexiconRepository(db_session)
    await lexicon_repo.upsert(
        LexiconEntry(
            id=None,
            term="prohibited_brand",
            normalized_term="prohibited_brand",
            category="prohibited",
            lang="en",
            severity="block",
            approved_by="DED_ADMIN",
        )
    )
    await db_session.commit()

    payload = {
        "NameAr": "اسم تجاري عادي",
        "NameEn": "Prohibited_Brand Trading",
        "RequestId": "REQ-003",
        "OperationType": "new",
    }
    resp = await client.post("/TradeName/ValidateWithSuggestion", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["decision"] == "BLOCKED"
    assert data["Prohibted"] is True
    assert any(r["category"] == "prohibited" and r["severity"] == "block" for r in data["reasons"])


@pytest.mark.asyncio
async def test_is_trade_name_exist_endpoint(client: AsyncClient, db_session: AsyncSession):
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=2001,
        normalized_ar="شركه الوفاء",
        normalized_en="al wafa company",
        phonetic_key="WF|WF",
        status="active",
        category_id=1,
    )
    await db_session.commit()

    # Matches existing active name
    resp = await client.get("/TradeName/IsTradeNameExist", params={"NameAr": "شركة الوفاء", "CategoryId": 1})
    assert resp.status_code == 200
    assert resp.json()["Exists"] is True

    # Exclude self by TradeNameId
    resp_excluded = await client.get(
        "/TradeName/IsTradeNameExist",
        params={"NameAr": "شركة الوفاء", "TradeNameId": 2001, "CategoryId": 1},
    )
    assert resp_excluded.status_code == 200
    assert resp_excluded.json()["Exists"] is False

    # Does not match non-existing name
    resp_none = await client.get("/TradeName/IsTradeNameExist", params={"NameEn": "Non Existing Name", "CategoryId": 1})
    assert resp_none.status_code == 200
    assert resp_none.json()["Exists"] is False


@pytest.mark.asyncio
async def test_search_endpoint(client: AsyncClient, db_session: AsyncSession):
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=3001,
        normalized_ar="شركه الخليج للالمنيوم",
        normalized_en="gulf aluminum company",
        phonetic_key="GLF|GLF",
        status="active",
    )
    await db_session.commit()

    resp = await client.get("/TradeName/Search", params={"Keyword": "gulf aluminum", "Limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert "Results" in data
    assert data["Total"] >= 1
    assert data["Results"][0]["registry_id"] == 3001


@pytest.mark.asyncio
async def test_admin_lexicon_crud_and_proposals(client: AsyncClient, db_session: AsyncSession):
    # 1. Create a proposal via admin entry endpoint (unapproved)
    create_payload = {
        "term": "test_risk_word",
        "category": "unfriendly",
        "lang": "en",
        "severity": "review",
        "approved_by": None,
    }
    create_resp = await client.post("/Admin/Lexicon/Entries", json=create_payload)
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    # 2. List pending proposals
    list_resp = await client.get("/Admin/Lexicon/Proposals")
    assert list_resp.status_code == 200
    assert any(p["id"] == entry_id for p in list_resp.json()["proposals"])

    # 3. Approve proposal
    action_payload = {
        "proposal_id": entry_id,
        "action": "approve",
        "approved_by": "SeniorAdmin",
    }
    approve_resp = await client.post("/Admin/Lexicon/Proposals", json=action_payload)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["approved_by"] == "SeniorAdmin"

    # 4. Verify no longer in pending list
    list_after = await client.get("/Admin/Lexicon/Proposals")
    assert not any(p["id"] == entry_id for p in list_after.json()["proposals"])


@pytest.mark.asyncio
async def test_register_trade_name_success(client: AsyncClient, db_session: AsyncSession):
    payload = {
        "NameAr": "مقهى النخبة المميز",
        "NameEn": "Elite Special Cafe",
        "CategoryId": 4,
        "LegalForm": "LLC",
    }
    resp = await client.post("/TradeName/Register", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["status"] == "registered"
    assert data["is_existing"] is False
    assert data["trade_name_id"] is not None
    assert data["reference_number"] is not None


@pytest.mark.asyncio
async def test_register_trade_name_duplicate_rejected(client: AsyncClient, db_session: AsyncSession):
    index_repo = TradeNameIndexRepository(db_session)
    await index_repo.upsert(
        trade_name_id=5001,
        normalized_ar="مقهى ومطعم تيجا",
        normalized_en="teja cafe and restaurant",
        phonetic_key="TJ|TJ",
        status="active",
        category_id=4,
    )
    await db_session.commit()

    payload = {
        "NameAr": "مقهى ومطعم تيجا",
        "NameEn": "Teja Cafe and Restaurant",
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
    # Suggestions must not repeat the conflicting existing brand token
    assert not any("teja" in s["name_en"].lower() for s in data["suggestions"])
