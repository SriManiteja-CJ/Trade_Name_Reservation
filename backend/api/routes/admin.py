"""
api/routes/admin.py
Admin routes for managing the lexicon and proposals (F4, E7, Phase 1.10, Phase 5).

Spec references:
  F4  — Word checks (prohibited, profanity, unfriendly, special, divine_name, location, family_name)
  E7  — LLM-proposed lexicon variants, approved by a human
  §5.2 — POST Admin/Lexicon/Proposals (approving/rejecting proposals, direct admin CRUD)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.admin import (
    GenerateVariantsRequest,
    GenerateVariantsResponse,
    LexiconEntryCreate,
    LexiconEntryResponse,
    LexiconProposalAction,
    LexiconProposalListResponse,
)
from db.models import Lexicon
from db.session import get_db
from lexicon.proposal_worker import LexiconProposalWorker
from lexicon.repository import LexiconEntry, LexiconRepository
from pipeline.normalizer import normalize_arabic, normalize_english

router = APIRouter(prefix="/Admin", tags=["Admin"])


@router.post(
    "/Lexicon/Proposals",
    response_model=LexiconEntryResponse,
    summary="Approve or reject a lexicon proposal (E7, Phase 1.10, Phase 5)",
)
async def process_proposal(
    action: LexiconProposalAction,
    db: AsyncSession = Depends(get_db),
) -> LexiconEntryResponse:
    """
    Approve or reject an LLM-proposed lexicon variant or entry.
    Every proposed variant requires explicit human approval before entering the lexicon (E7).
    """
    worker = LexiconProposalWorker(db)
    reviewer_name = action.get_reviewer()

    if action.action == "approve":
        approved_entry = await worker.approve_proposal(action.proposal_id, reviewer_name)
        if not approved_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lexicon proposal ID {action.proposal_id} not found",
            )
        return LexiconEntryResponse(
            id=approved_entry.id,
            term=approved_entry.term,
            normalized_term=approved_entry.normalized_term,
            category=approved_entry.category,
            lang=approved_entry.lang,
            severity=approved_entry.severity,
            variants=approved_entry.variants,
            approved_by=approved_entry.approved_by,
            created_at=approved_entry.created_at,
            updated_at=approved_entry.updated_at,
        )
    elif action.action == "reject":
        rejected_info = await worker.reject_proposal(action.proposal_id)
        if not rejected_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lexicon proposal ID {action.proposal_id} not found",
            )
        return LexiconEntryResponse(
            id=action.proposal_id,
            term=rejected_info["term"],
            normalized_term=rejected_info["term"],
            category=rejected_info["category"],
            lang=rejected_info["lang"],
            severity="block",
            variants=rejected_info.get("variants"),
            approved_by="REJECTED",
        )


@router.get(
    "/Lexicon/Proposals",
    response_model=LexiconProposalListResponse,
    summary="List pending lexicon proposals awaiting human approval",
)
async def list_proposals(
    db: AsyncSession = Depends(get_db),
) -> LexiconProposalListResponse:
    """
    List all pending lexicon proposals where approved_by is null.
    """
    repo = LexiconRepository(db)
    pending = await repo.list_pending_proposals()
    items = [
        LexiconEntryResponse(
            id=e.id,
            term=e.term,
            normalized_term=e.normalized_term,
            category=e.category,
            lang=e.lang,
            severity=e.severity,
            variants=e.variants,
            approved_by=e.approved_by,
        )
        for e in pending
    ]
    return LexiconProposalListResponse(proposals=items, total=len(items))


@router.post(
    "/Lexicon/ProposeVariants",
    response_model=GenerateVariantsResponse,
    summary="Propose evasion and phonetic variants for a compliance term (Stage ⑨, E7)",
)
async def propose_variants(
    request: GenerateVariantsRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateVariantsResponse:
    """
    Generates proposed phonetic, typo, and Arabizi evasion variants for a compliance term (E7).
    """
    worker = LexiconProposalWorker(db)
    variants = await worker.generate_variants(
        term=request.term,
        category=request.category,
        lang=request.lang,
    )
    return GenerateVariantsResponse(
        term=request.term,
        variants=variants,
        count=len(variants),
    )


@router.post(
    "/Lexicon/Entries",
    response_model=LexiconEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Direct admin creation or update of a lexicon term",
)
async def create_or_update_entry(
    payload: LexiconEntryCreate,
    db: AsyncSession = Depends(get_db),
) -> LexiconEntryResponse:
    """
    Create or update an entry in the Lexicon table.
    Normalizes the term before storing.
    If auto_propose_variants is True, automatically proposes phonetic variants via Stage ⑨ (E7).
    """
    worker = LexiconProposalWorker(db)

    if payload.auto_propose_variants:
        entry = await worker.create_term_proposal(
            term=payload.term,
            category=payload.category,
            lang=payload.lang,
            severity=payload.severity,
            custom_variants=payload.variants,
            auto_generate_variants=True,
            approved_by=payload.approved_by,
        )
        return LexiconEntryResponse(
            id=entry.id,
            term=entry.term,
            normalized_term=entry.normalized_term,
            category=entry.category,
            lang=entry.lang,
            severity=entry.severity,
            variants=entry.variants,
            approved_by=entry.approved_by,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )

    # Standard direct creation
    repo = LexiconRepository(db)
    norm = normalize_arabic(payload.term) if payload.lang == "ar" else normalize_english(payload.term)

    lex_entry = LexiconEntry(
        id=None,
        term=payload.term,
        normalized_term=norm,
        category=payload.category,
        lang=payload.lang,
        severity=payload.severity,
        variants=payload.variants or [],
        approved_by=payload.approved_by,
    )
    upserted = await repo.upsert(lex_entry)
    return LexiconEntryResponse(
        id=upserted.id,
        term=upserted.term,
        normalized_term=upserted.normalized_term,
        category=upserted.category,
        lang=upserted.lang,
        severity=upserted.severity,
        variants=upserted.variants,
        approved_by=upserted.approved_by,
    )


@router.get(
    "/Lexicon/Entries",
    response_model=list[LexiconEntryResponse],
    summary="List lexicon entries by category",
)
async def list_entries_by_category(
    category: str = Query(..., description="F4 category"),
    db: AsyncSession = Depends(get_db),
) -> list[LexiconEntryResponse]:
    repo = LexiconRepository(db)
    entries = await repo.list_all_by_category(category)
    return [
        LexiconEntryResponse(
            id=e.id,
            term=e.term,
            normalized_term=e.normalized_term,
            category=e.category,
            lang=e.lang,
            severity=e.severity,
            variants=e.variants,
            approved_by=e.approved_by,
        )
        for e in entries
    ]
