"""
api/schemas/admin.py
Pydantic v2 schemas for the Admin Lexicon endpoints (F4, E7, Phase 1.10).
"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class LexiconEntryCreate(BaseModel):
    """Admin direct creation or proposal of a lexicon term."""
    term: str = Field(..., description="Raw word or phrase")
    category: Literal[
        "prohibited", "profanity", "unfriendly", "special",
        "divine_name", "location", "family_name"
    ] = Field(..., description="F4 category")
    lang: Literal["ar", "en", "both"] = Field(..., description="Language scope")
    severity: Literal["block", "review", "info"] = Field(..., description="block | review | info")
    variants: Optional[list[str]] = Field(default=None, description="Known variants / misspellings")
    approved_by: Optional[str] = Field(None, description="Reviewer name (null if pending proposal)")
    auto_propose_variants: bool = Field(default=False, description="Automatically propose variants via Stage 9 (E7)")


class LexiconProposalAction(BaseModel):
    """Admin action on a lexicon proposal (approve / reject) (spec §5.2)."""
    proposal_id: int = Field(..., description="ID of the lexicon entry / proposal")
    action: Literal["approve", "reject"] = Field(..., description="approve | reject")
    approved_by: Optional[str] = Field(default=None, description="Admin username or employee ID")
    reviewer: Optional[str] = Field(default=None, description="Reviewer name per spec §5.2")

    def get_reviewer(self) -> str:
        return self.reviewer or self.approved_by or "DED_Admin"


class GenerateVariantsRequest(BaseModel):
    """Request to propose variants for a term (Stage ⑨, E7)."""
    term: str = Field(..., description="Term to expand")
    category: str = Field(default="prohibited", description="Category")
    lang: Literal["ar", "en", "both"] = Field(default="en", description="Language")


class GenerateVariantsResponse(BaseModel):
    """Response containing proposed evasion variants."""
    term: str
    variants: list[str]
    count: int


class LexiconEntryResponse(BaseModel):
    """Response representing a lexicon entry."""
    id: int
    term: str
    normalized_term: str
    category: str
    lang: str
    severity: str
    variants: Optional[list[str]] = None
    approved_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LexiconProposalListResponse(BaseModel):
    """Response containing pending or reviewed proposals."""
    proposals: list[LexiconEntryResponse]
    total: int

