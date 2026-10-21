"""
api/schemas/validation.py
Pydantic v2 request/response schemas for the validation endpoints.

Preserves ALL existing legacy response fields (N9 — additive only).
Adds new fields: decision, reasons[], similarNames[], activityFit (spec §5.2).

Spec references:
  F1  — both AR and EN name forms present in request
  F2  — excludes current record via TradeNameId
  F13 — operation_type distinguishes new/edit/renew/branch/legal_form_amend
  F14 — lang header for response language selection
  N4  — reasons always bilingual
  N9  — existing fields preserved exactly (including typo "Prohibted")
  §5.2 — endpoint contract: POST TradeName/ValidateWithSuggestion
"""
from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------
class ValidateRequest(BaseModel):
    """
    Request body for POST TradeName/ValidateWithSuggestion.
    Fields match the existing DED API contract; new optional fields added.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Core name fields (F1)
    NameAr: str = Field(
        ...,
        validation_alias=AliasChoices("NameAr", "TradeNameArabic", "name_ar"),
        description="Arabic trade name",
    )
    NameEn: str = Field(
        ...,
        validation_alias=AliasChoices("NameEn", "TradeNameEnglish", "name_en"),
        description="English trade name",
    )

    # Activity category (E3, E6, F15)
    ActivityCategoryId: Optional[int] = Field(
        None,
        validation_alias=AliasChoices("ActivityCategoryId", "ActivityCategory", "activity_category_id", "activity_category"),
        description="Activity category ID",
    )

    # Legal form
    LegalForm: Optional[str] = Field(None, description="Legal form token")

    # Real DED application request ID (N3)
    RequestId: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("RequestId", "requestId", "request_id"),
        description="Real DED application request ID",
    )

    # Operation type (F13: new|edit|renew|branch|legal_form_amend)
    OperationType: str = Field(
        default="new",
        description="new | edit | renew | branch | legal_form_amend",
    )

    # For edit/renew/amend: ID of the existing record to exclude from F2 check
    # (Ambiguity #7: must be provided for edit/renew operations)
    TradeNameId: Optional[int] = Field(
        None,
        description="ID of the existing trade name record (required for edit/renew/amend)",
    )

    # F10: branch outside UAQ flag
    IsOutsideUAQ: Optional[bool] = Field(False, description="True for outside-UAQ branch (F10)")

    # F11: legal-form amendment
    OldLegalForm: Optional[str] = Field(None, description="Old legal-form token (F11 amendment)")
    NewLegalForm: Optional[str] = Field(None, description="New legal-form token (F11 amendment)")

    # F12: previous name for unchanged-name detection
    PreviousNameAr: Optional[str] = Field(None, description="Previous Arabic name (F12 detection)")
    PreviousNameEn: Optional[str] = Field(None, description="Previous English name (F12 detection)")

    # Existing fields (preserved for N9 compatibility)
    Channel: Optional[str] = Field(None, description="online | walkin (also read from JWT)")

    model_config = ConfigDict(extra="allow")


class IsTradeNameExistRequest(BaseModel):
    """GET TradeName/IsTradeNameExist query params."""
    NameAr: Optional[str] = None
    NameEn: Optional[str] = None
    TradeNameId: Optional[int] = None  # exclude current record (Ambiguity #7)


class SearchRequest(BaseModel):
    """GET TradeName/Search query params."""
    Keyword: str = Field(..., description="Search keyword (stored in both languages per F22)")
    Limit: int = Field(default=10, ge=1, le=50)


# ---------------------------------------------------------------------------
# Shared response building blocks
# ---------------------------------------------------------------------------
class ReasonResponse(BaseModel):
    """
    A single bilingual reason+fix entry (N4).
    Maps to spec §4.2 RiskOutput structure.
    """
    category: str
    severity: str          # "block" | "review" | "info"
    language: str          # "ar" | "en" | "both"
    reason_en: str
    reason_ar: str
    fix_en: str
    fix_ar: str
    source: str = "deterministic"


class SimilarNameResponse(BaseModel):
    """One similar name entry in the similarNames[] list."""
    registry_id: int
    normalized_ar: str
    normalized_en: str
    similarity_score: float
    confusingly_similar: Optional[bool] = None
    reason_en: Optional[str] = None
    reason_ar: Optional[str] = None


class ActivityFitResponse(BaseModel):
    """Activity fit verdict (E3, spec §4.2 activity_fit)."""
    fits: bool
    suggested_category_code: Optional[str] = None
    reason_en: str = ""
    reason_ar: str = ""


class SuggestionResponseItem(BaseModel):
    """A suggestion item returned in ValidateWithSuggestion (Stage ⑥, F8, F17)."""
    name_ar: str
    name_en: str
    score: float = 1.0
    source: str = "llm"
    database_verified: bool = True


# ---------------------------------------------------------------------------
# Response model — ValidateWithSuggestion
# ---------------------------------------------------------------------------
class ValidateResponse(BaseModel):
    """
    Response for POST TradeName/ValidateWithSuggestion.

    LEGACY FIELDS (N9 — must be present and correct regardless of AI flag):
      Prohibted, Profanity, Unfriendly, Special, AllahNames, LocationNames,
      FamilyNames — boolean flags from lexicon checks
      Similarity — float (highest similarity score)

    NEW ADDITIVE FIELDS (spec §5.2):
      decision    — OK | NEEDS_REVIEW | BLOCKED
      reasons     — list of bilingual reason+fix objects
      similarNames — top similar names
      activityFit  — activity fit verdict
      suggestions — top 10 verified unreserved alternatives (Stage ⑥)

    Note: "Prohibted" is intentionally misspelled to match the existing API contract.
    """
    # ----- Legacy boolean fields (N9 — exact field names preserved) -------
    Prohibted: bool = False          # Note: intentional spec typo preserved
    Profanity: bool = False
    Unfriendly: bool = False
    Special: bool = False
    AllahNames: bool = False
    LocationNames: bool = False
    FamilyNames: bool = False
    Similarity: float = 0.0

    # ----- New additive fields (spec §5.2) --------------------------------
    decision: str = "OK"             # OK | NEEDS_REVIEW | BLOCKED
    reasons: list[ReasonResponse] = Field(default_factory=list)
    similarNames: list[SimilarNameResponse] = Field(default_factory=list)
    activityFit: Optional[ActivityFitResponse] = None
    suggestions: list[SuggestionResponseItem] = Field(default_factory=list)

    # Direct database existence & conflict flags (Requirements 1, 2, 5)
    is_existing: bool = False
    matched_name_ar: Optional[str] = None
    matched_name_en: Optional[str] = None
    conflict_type: Optional[str] = None  # exact_duplicate | reserved_base_name | confusingly_similar | generic_name
    protected_base_name: Optional[str] = None
    registered_category_id: Optional[int] = None
    registered_activity_name_en: Optional[str] = None
    registered_activity_name_ar: Optional[str] = None

    model_config = ConfigDict(extra="allow")



class IsTradeNameExistResponse(BaseModel):
    """Response for GET TradeName/IsTradeNameExist."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    Exists: bool
    MatchedNameAr: Optional[str] = None
    MatchedNameEn: Optional[str] = None
    ConflictType: Optional[str] = None
    ProtectedBaseName: Optional[str] = None
    RegisteredCategoryId: Optional[int] = None
    RegisteredActivityNameEn: Optional[str] = None
    RegisteredActivityNameAr: Optional[str] = None
    AvailabilityStatus: str = "available"
    NeedsReview: bool = False

    # Lowercase aliases for convenience
    exists: Optional[bool] = None
    matched_name_ar: Optional[str] = None
    matched_name_en: Optional[str] = None
    conflict_type: Optional[str] = None
    protected_base_name: Optional[str] = None
    registered_category_id: Optional[int] = None
    registered_activity_name_en: Optional[str] = None
    registered_activity_name_ar: Optional[str] = None
    availability_status: str = "available"
    needs_review: bool = False


class RegisterTradeNameRequest(BaseModel):
    """Request model for POST TradeName/Register."""
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    NameAr: str = Field(..., validation_alias=AliasChoices("NameAr", "TradeNameArabic", "name_ar"))
    NameEn: str = Field(..., validation_alias=AliasChoices("NameEn", "TradeNameEnglish", "name_en"))
    LegalForm: Optional[str] = Field("LIMITED LIABILITY COMPANY", validation_alias=AliasChoices("LegalForm", "legal_form"), description="Legal form token")
    ActivityCategoryId: Optional[int] = Field(None, validation_alias=AliasChoices("ActivityCategoryId", "CategoryId", "category_id"), description="Activity category ID")
    TradeNameId: Optional[int] = Field(None, validation_alias=AliasChoices("TradeNameId", "trade_name_id"), description="Trade name ID to exclude if updating")
    ApplicantId: Optional[str] = Field(None, description="Applicant ID")
    Channel: Optional[str] = Field("online", description="Channel")


class RegisterTradeNameResponse(BaseModel):
    """Response model for POST TradeName/Register."""
    model_config = ConfigDict(extra="allow")

    success: bool
    status: str  # "REGISTERED" | "REJECTED_ALREADY_EXISTS" | "REJECTED_LEXICON_BLOCK"
    reference_number: Optional[str] = None
    trade_name_id: Optional[int] = None
    name_ar: Optional[str] = ""
    name_en: Optional[str] = ""
    is_existing: Optional[bool] = False
    conflict_type: Optional[str] = None
    protected_base_name: Optional[str] = None
    registered_category_id: Optional[int] = None
    registered_activity_name_en: Optional[str] = None
    registered_activity_name_ar: Optional[str] = None
    message_en: str
    message_ar: str
    suggestions: list[SuggestionResponseItem] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Response for GET TradeName/Search."""
    Results: list[SimilarNameResponse] = Field(default_factory=list)
    Total: int = 0


# ---------------------------------------------------------------------------
# Transliteration endpoint schemas (Phase 3, F7)
# ---------------------------------------------------------------------------
class CheckTransliterationRequest(BaseModel):
    """POST TradeName/CheckTransliteration — F7."""
    NameAr: str
    NameEn: str
    OriginalNameAr: Optional[str] = None
    OriginalNameEn: Optional[str] = None


class CheckTransliterationResponse(BaseModel):
    consistent: bool
    confidence: float
    expected_en: str = ""
    expected_ar: str = ""


class TransliterateRequest(BaseModel):
    """POST TradeName/Transliterate — Bidirectional English <-> Arabic transliteration and translation."""
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    NameEn: Optional[str] = Field(None, validation_alias=AliasChoices("NameEn", "name_en", "english_name", "englishName"))
    NameAr: Optional[str] = Field(None, validation_alias=AliasChoices("NameAr", "name_ar", "arabic_name", "arabicName"))


class TransliterateResponse(BaseModel):
    """Response model for POST TradeName/Transliterate."""
    name_en: str
    arabic_name: str
    confidence: float = 0.95


# ---------------------------------------------------------------------------
# SuggestCategory endpoint schemas (Phase 3, E6)
# ---------------------------------------------------------------------------
class SuggestCategoryRequest(BaseModel):
    """POST TradeName/SuggestCategory — E6 with Activity Type Mismatch & Clarification."""
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    NameAr: Optional[str] = Field("", validation_alias=AliasChoices("NameAr", "TradeNameArabic", "name_ar"))
    NameEn: Optional[str] = Field("", validation_alias=AliasChoices("NameEn", "TradeNameEnglish", "name_en"))
    ActivityType: Optional[str] = Field("", validation_alias=AliasChoices("ActivityType", "activity_type", "activityType", "activity"))
    ActivityCategoryId: Optional[int] = Field(None, validation_alias=AliasChoices("ActivityCategoryId", "activity_category_id", "categoryId"))
    UserContext: Optional[str] = Field(None, validation_alias=AliasChoices("UserContext", "user_context", "clarification"))


class SuggestCategoryResponse(BaseModel):
    status: str = "match"  # match | mismatch | generic_activity | clarification_needed
    is_match: bool = True
    mismatch_detected: bool = False
    clarification_needed: bool = False
    clarification_question_en: Optional[str] = None
    clarification_question_ar: Optional[str] = None
    original_activity: Optional[str] = None
    suggested_category_code: Optional[str] = None
    category_id: Optional[int] = None
    suggested_activity_type: Optional[str] = None
    suggested_activities: list[str] = Field(default_factory=list)
    activity_categories: list[dict] = Field(default_factory=list)
    recommended_trade_names: list[dict] = Field(default_factory=list)
    reason_en: str = ""
    reason_ar: str = ""
    verified: bool = True


# ---------------------------------------------------------------------------
# ReviewerBrief endpoint schemas (Phase 4, E5)
# ---------------------------------------------------------------------------
class ReviewerBriefResponse(BaseModel):
    """GET TradeName/ReviewerBrief/{requestId} — E5."""
    request_id: str
    flags: list[ReasonResponse] = Field(default_factory=list)
    top_similar: list[SimilarNameResponse] = Field(default_factory=list)
    transliteration_verdict: Optional[CheckTransliterationResponse] = None
    activity_fit_verdict: Optional[ActivityFitResponse] = None
    recommendation: str = ""   # approve | reject | return | ssp_committee
    draft_admin_comments_en: str = ""
    draft_admin_comments_ar: str = ""
    generated_on: str = ""
    reviewer_decision: Optional[str] = None


class ReviewerDecisionRequest(BaseModel):
    """POST TradeName/ReviewerDecision — F20, N7."""
    request_id: str
    decision: str  # approve | reject | return | ssp_committee
    reviewer_id: Optional[str] = "DED_OFFICER_1"
    notes: Optional[str] = None


class ReviewerDecisionResponse(BaseModel):
    request_id: str
    decision: str
    updated: bool = True


# ---------------------------------------------------------------------------
# RegisterTradeName endpoint schemas
# ---------------------------------------------------------------------------
class RegisterTradeNameRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    NameAr: Optional[str] = Field(None, validation_alias=AliasChoices("NameAr", "name_ar", "TradeNameArabic"))
    NameEn: Optional[str] = Field(None, validation_alias=AliasChoices("NameEn", "name_en", "TradeNameEnglish"))
    CategoryId: Optional[int] = Field(None, validation_alias=AliasChoices("CategoryId", "category_id", "ActivityCategory", "ActivityCategoryId"))
    TradeNameId: Optional[int] = Field(None, validation_alias=AliasChoices("TradeNameId", "trade_name_id", "TradeNameID"))
    ApplicantName: Optional[str] = Field(None, validation_alias=AliasChoices("ApplicantName", "applicant_name"))
    ReferenceNumber: Optional[str] = Field(None, validation_alias=AliasChoices("ReferenceNumber", "reference_number"))
    OperationType: Optional[str] = Field("new", validation_alias=AliasChoices("OperationType", "operation_type"))
    LegalForm: Optional[str] = Field(None, validation_alias=AliasChoices("LegalForm", "legal_form"))

    @property
    def name_ar(self) -> Optional[str]:
        return self.NameAr

    @property
    def name_en(self) -> Optional[str]:
        return self.NameEn

    @property
    def category_id(self) -> Optional[int]:
        return self.CategoryId

    @property
    def trade_name_id(self) -> Optional[int]:
        return self.TradeNameId

    @property
    def legal_form(self) -> Optional[str]:
        return self.LegalForm

    @property
    def reference_number(self) -> Optional[str]:
        return self.ReferenceNumber
