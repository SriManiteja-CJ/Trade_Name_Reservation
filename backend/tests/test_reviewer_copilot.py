"""
tests/test_reviewer_copilot.py
Unit and integration tests for Phase 4: Stage ⑧ Reviewer Copilot.
Spec references:
  E5  — Reviewer copilot brief per submission
  F20 — Support reviewer actions: approve, reject, return, ssp_committee
  N7  — Quality feedback loop from reviewer decisions
  N8  — Bounded cost: single LLM call or deterministic fallback
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import FlagMode, get_settings
from copilot.brief_worker import ReviewerCopilotService
from llm.schemas import ReviewerBriefOutput

settings = get_settings()


# ---------------------------------------------------------------------------
# 1. ReviewerCopilotService Unit Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reviewer_copilot_service_deterministic(db_session: AsyncSession):
    """
    Test ReviewerCopilotService baseline deterministic rules:
    - BLOCKED -> 'reject'
    - NEEDS_REVIEW (location / special) -> 'ssp_committee'
    - NEEDS_REVIEW (other) -> 'return'
    - APPROVED -> 'approve'
    """
    service = ReviewerCopilotService(db_session)

    # 1. BLOCKED
    brief_blocked = await service.generate_brief(
        request_id="REQ-BLK-1",
        name_ar="شركة وهمية",
        name_en="Fake Company",
        decision="BLOCKED",
        flags=[{"code": "PROHIBITED_WORD", "reason_en": "Prohibited term", "category": "prohibited"}],
        similar_names=[],
    )
    assert brief_blocked.brief_json["recommendation"] == "reject"
    assert "rejected" in brief_blocked.brief_json["draft_admin_comments_en"].lower()

    # 2. NEEDS_REVIEW with location
    brief_ssp = await service.generate_brief(
        request_id="REQ-SSP-1",
        name_ar="أم القيوين للتجارة",
        name_en="UAQ Trading",
        decision="NEEDS_REVIEW",
        flags=[{"code": "LOCATION_NAME", "reason_en": "Location name used", "category": "location"}],
        similar_names=[],
    )
    assert brief_ssp.brief_json["recommendation"] == "ssp_committee"
    assert "SSP" in brief_ssp.brief_json["draft_admin_comments_en"]

    # 3. NEEDS_REVIEW standard (return)
    brief_return = await service.generate_brief(
        request_id="REQ-RET-1",
        name_ar="السرعة لخدمات السيارات",
        name_en="Speed Car Services",
        decision="NEEDS_REVIEW",
        flags=[{"code": "HIGH_SIMILARITY", "reason_en": "High similarity with active name", "category": "similarity"}],
        similar_names=[{"registry_id": 10, "normalized_ar": "السرعة للسيارات", "normalized_en": "SPEED CARS", "similarity_score": 0.88}],
    )
    assert brief_return.brief_json["recommendation"] == "return"
    assert "returned" in brief_return.brief_json["draft_admin_comments_en"].lower()

    # 4. APPROVED
    brief_app = await service.generate_brief(
        request_id="REQ-APP-1",
        name_ar="الابتكار للتقنية",
        name_en="Innovation Tech",
        decision="APPROVED",
        flags=[],
        similar_names=[],
    )
    assert brief_app.brief_json["recommendation"] == "approve"
    assert "satisfies all ded requirements" in brief_app.brief_json["draft_admin_comments_en"].lower()

    # 5. Retrieve existing brief
    fetched = await service.get_brief("REQ-APP-1")
    assert fetched is not None
    assert fetched.request_id == "REQ-APP-1"

    # 6. Record decision for feedback loop (N7)
    updated = await service.record_decision("REQ-APP-1", "approve")
    assert updated is not None
    assert updated.reviewer_decision == "approve"

    # 7. Record decision for non-existent request
    none_res = await service.record_decision("NON-EXISTENT", "approve")
    assert none_res is None


@pytest.mark.asyncio
async def test_reviewer_copilot_service_llm_mode(db_session: AsyncSession):
    """
    Test ReviewerCopilotService when LLM brief generation is enabled.
    """
    original_flag = settings.ai_reviewer_brief
    settings.ai_reviewer_brief = FlagMode.on

    mock_llm_brief = ReviewerBriefOutput(
        recommendation="ssp_committee",
        draft_admin_comments_en="Special Scrutiny Panel approval required due to geographic sensitivity.",
        draft_admin_comments_ar="يتطلب موافقة لجنة التدقيق الخاصة نظراً للطبيعة الجغرافية للاسم.",
        flag_summary=["Geographic designation detected"],
    )

    try:
        with patch("copilot.brief_worker.LlmGateway.generate_brief", new_callable=AsyncMock) as mock_gen, \
             patch("copilot.brief_worker.LlmGateway.close", new_callable=AsyncMock):
            mock_gen.return_value = mock_llm_brief

            service = ReviewerCopilotService(db_session)
            brief = await service.generate_brief(
                request_id="REQ-LLM-01",
                name_ar="أم القيوين للتجارة العامة",
                name_en="UAQ General Trading",
                decision="NEEDS_REVIEW",
                flags=[{"code": "LOCATION", "reason_en": "Location name", "category": "location"}],
                similar_names=[],
            )

            assert brief.brief_json["recommendation"] == "ssp_committee"
            assert brief.brief_json["draft_admin_comments_en"] == mock_llm_brief.draft_admin_comments_en
            assert brief.brief_json["draft_admin_comments_ar"] == mock_llm_brief.draft_admin_comments_ar
    finally:
        settings.ai_reviewer_brief = original_flag


# ---------------------------------------------------------------------------
# 2. HTTP Endpoint Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reviewer_brief_endpoint_404(client: AsyncClient):
    """
    GET /TradeName/ReviewerBrief/{requestId}: Returns 404 for unknown request.
    """
    resp = await client.get("/TradeName/ReviewerBrief/UNKNOWN_REQ_999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reviewer_decision_endpoint_invalid(client: AsyncClient):
    """
    POST /TradeName/ReviewerDecision: Returns 400 for invalid action.
    """
    resp = await client.post(
        "/TradeName/ReviewerDecision",
        json={"request_id": "REQ-123", "decision": "super_approve"},
    )
    assert resp.status_code == 400
    assert "invalid decision" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reviewer_decision_endpoint_404(client: AsyncClient):
    """
    POST /TradeName/ReviewerDecision: Returns 404 when request_id does not exist.
    """
    resp = await client.post(
        "/TradeName/ReviewerDecision",
        json={"request_id": "NON_EXISTENT_ID", "decision": "approve"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_full_reviewer_copilot_workflow(client: AsyncClient):
    """
    End-to-end integration workflow for Stage ⑧ Reviewer Copilot:
    1. Submit ValidateWithSuggestion with RequestId
    2. Check GET /TradeName/ReviewerBrief/{requestId} returns generated brief
    3. Submit POST /TradeName/ReviewerDecision to record reviewer action
    4. Verify GET /TradeName/ReviewerBrief/{requestId} reflects reviewer decision
    """
    original_brief_flag = settings.ai_reviewer_brief
    # Use shadow/on mode to trigger brief generation in ValidateWithSuggestion
    settings.ai_reviewer_brief = FlagMode.shadow

    req_id = "WORKFLOW-REQ-100"
    payload = {
        "RequestId": req_id,
        "NameAr": "مخبز الأمل الحديث",
        "NameEn": "Modern Hope Bakery",
        "ActivityCodes": ["BAKE_001"],
        "LegalForm": "LLC",
    }

    try:
        # Step 1: ValidateWithSuggestion triggers brief generation
        val_resp = await client.post("/TradeName/ValidateWithSuggestion", json=payload)
        assert val_resp.status_code == 200

        # Step 2: Fetch brief
        brief_resp = await client.get(f"/TradeName/ReviewerBrief/{req_id}")
        assert brief_resp.status_code == 200
        brief_data = brief_resp.json()

        assert brief_data["request_id"] == req_id
        assert brief_data["recommendation"] in ("approve", "reject", "return", "ssp_committee")
        assert len(brief_data["draft_admin_comments_en"]) > 0
        assert len(brief_data["draft_admin_comments_ar"]) > 0
        assert brief_data["reviewer_decision"] is None

        # Step 3: Record human reviewer decision (approve)
        dec_resp = await client.post(
            "/TradeName/ReviewerDecision",
            json={"request_id": req_id, "decision": "approve"},
        )
        assert dec_resp.status_code == 200
        assert dec_resp.json()["updated"] is True
        assert dec_resp.json()["decision"] == "approve"

        # Step 4: Verify brief now contains the recorded reviewer decision
        brief_resp_2 = await client.get(f"/TradeName/ReviewerBrief/{req_id}")
        assert brief_resp_2.status_code == 200
        assert brief_resp_2.json()["reviewer_decision"] == "approve"

    finally:
        settings.ai_reviewer_brief = original_brief_flag
