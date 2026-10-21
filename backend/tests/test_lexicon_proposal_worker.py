"""
tests/test_lexicon_proposal_worker.py
Unit and integration tests for Stage ⑨ Lexicon Manager & Proposal Worker (Phase 5).

Spec references:
  E7  — LLM-proposed lexicon variants, human-approved before entering lexicon
  F4  — Word checks (prohibited, profanity, unfriendly, special, divine_name, location, family_name)
  §5.2 — POST Admin/Lexicon/Proposals
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import FlagMode, get_settings
from db.models import Lexicon
from lexicon.proposal_worker import LexiconProposalWorker
from llm.schemas import LexiconVariantsOutput

settings = get_settings()


# ---------------------------------------------------------------------------
# 1. LexiconProposalWorker Unit Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_deterministic_variant_generation():
    """
    Test deterministic letter substitutions, Arabizi mappings, and evasion permutations.
    """
    worker = LexiconProposalWorker(session=None)  # Session not needed for static method

    # English term substitutions
    vars_en = worker.generate_deterministic_variants("casino", lang="en")
    assert any("kasino" in v for v in vars_en) or any("cazino" in v for v in vars_en)
    assert "casino" not in vars_en

    # Arabic term Arabizi mapping (ح -> 7)
    vars_ar = worker.generate_deterministic_variants("حلال", lang="ar")
    assert any("7" in v for v in vars_ar)
    assert "حلال" not in vars_ar


@pytest.mark.asyncio
async def test_generate_variants_llm_mode(db_session: AsyncSession):
    """
    Test variant generation with LLM Gateway mocked in on/shadow mode.
    """
    original_flag = settings.ai_analyzer
    settings.ai_analyzer = FlagMode.on

    mock_llm_output = LexiconVariantsOutput(
        term="betting",
        variants=["bett1ng", "beting", "b3tting"],
        reasoning="Common evasion substitutions in online chat.",
    )

    try:
        with patch("lexicon.proposal_worker.LlmGateway.generate_lexicon_variants", new_callable=AsyncMock) as mock_gen, \
             patch("lexicon.proposal_worker.LlmGateway.close", new_callable=AsyncMock):
            mock_gen.return_value = mock_llm_output

            worker = LexiconProposalWorker(db_session)
            variants = await worker.generate_variants(
                term="betting",
                category="prohibited",
                lang="en",
            )

            assert "bett1ng" in variants
            assert "b3tting" in variants
            assert "betting" not in variants
    finally:
        settings.ai_analyzer = original_flag


@pytest.mark.asyncio
async def test_proposal_lifecycle_pending_approve_reject(db_session: AsyncSession):
    """
    Test full proposal workflow in worker:
    1. Create pending proposal (approved_by is None)
    2. Verify it is held in pending queue
    3. Approve proposal -> approved_by set to reviewer
    4. Reject another proposal -> deleted from table
    """
    worker = LexiconProposalWorker(db_session)

    # 1. Create pending proposal
    entry1 = await worker.create_term_proposal(
        term="cazino",
        category="prohibited",
        lang="en",
        severity="block",
        custom_variants=["kazzino"],
        auto_generate_variants=False,
        approved_by=None,
    )
    assert entry1.id is not None
    assert entry1.approved_by is None
    assert "kazzino" in entry1.variants

    # 2. Approve proposal
    approved = await worker.approve_proposal(entry1.id, reviewer="Senior_Compliance_Lead")
    assert approved is not None
    assert approved.approved_by == "Senior_Compliance_Lead"

    # 3. Create second proposal to reject
    entry2 = await worker.create_term_proposal(
        term="borderline_word",
        category="special",
        lang="en",
        severity="review",
        auto_generate_variants=False,
        approved_by=None,
    )
    rejected_info = await worker.reject_proposal(entry2.id)
    assert rejected_info is not None
    assert rejected_info["term"] == "borderline_word"

    # Confirm deleted
    approved_none = await worker.approve_proposal(entry2.id, reviewer="Lead")
    assert approved_none is None


# ---------------------------------------------------------------------------
# 2. Admin API Endpoint Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_propose_variants_endpoint(client: AsyncClient):
    """
    POST /Admin/Lexicon/ProposeVariants: Generates candidate variants for UI review.
    """
    resp = await client.post(
        "/Admin/Lexicon/ProposeVariants",
        json={"term": "casino", "category": "prohibited", "lang": "en"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["term"] == "casino"
    assert isinstance(data["variants"], list)
    assert data["count"] == len(data["variants"])
    assert data["count"] > 0


@pytest.mark.asyncio
async def test_create_entry_with_auto_variants(client: AsyncClient):
    """
    POST /Admin/Lexicon/Entries with auto_propose_variants=True:
    Generates and stores variants into the Lexicon table.
    """
    resp = await client.post(
        "/Admin/Lexicon/Entries",
        json={
            "term": "gambling",
            "category": "prohibited",
            "lang": "en",
            "severity": "block",
            "auto_propose_variants": True,
            "approved_by": None,  # Pending human approval (E7)
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["term"] == "gambling"
    assert data["approved_by"] is None
    assert isinstance(data["variants"], list)
    assert len(data["variants"]) > 0


@pytest.mark.asyncio
async def test_admin_proposal_approval_flow(client: AsyncClient):
    """
    Test E7 end-to-end admin proposal approval & rejection API flow:
    1. Create a pending proposal
    2. GET /Admin/Lexicon/Proposals lists it
    3. POST /Admin/Lexicon/Proposals with action=approve approves it
    4. Second proposal with action=reject deletes it
    """
    # 1. Create pending entry
    create_resp = await client.post(
        "/Admin/Lexicon/Entries",
        json={
            "term": "lottery",
            "category": "prohibited",
            "lang": "en",
            "severity": "block",
            "variants": ["lotery", "lotteri"],
            "approved_by": None,
        },
    )
    prop_id = create_resp.json()["id"]

    # 2. List proposals
    list_resp = await client.get("/Admin/Lexicon/Proposals")
    assert list_resp.status_code == 200
    props = list_resp.json()["proposals"]
    assert any(p["id"] == prop_id for p in props)

    # 3. Approve proposal using spec §5.2 request shape: {"proposal_id": id, "action": "approve", "reviewer": "name"}
    app_resp = await client.post(
        "/Admin/Lexicon/Proposals",
        json={"proposal_id": prop_id, "action": "approve", "reviewer": "DED_SeniorReviewer"},
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["approved_by"] == "DED_SeniorReviewer"

    # 4. Create another pending proposal to test rejection
    create_resp_2 = await client.post(
        "/Admin/Lexicon/Entries",
        json={
            "term": "false_positive",
            "category": "unfriendly",
            "lang": "en",
            "severity": "review",
            "approved_by": None,
        },
    )
    prop_id_2 = create_resp_2.json()["id"]

    rej_resp = await client.post(
        "/Admin/Lexicon/Proposals",
        json={"proposal_id": prop_id_2, "action": "reject", "reviewer": "DED_Reviewer"},
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["approved_by"] == "REJECTED"
