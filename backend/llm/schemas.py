"""
llm/schemas.py
Pydantic v2 models for the LLM Analyzer output contract (spec §4.2).

The LLM is expected to return a single JSON object conforming to
LlmAnalyzerOutput. vLLM's guided JSON decoding enforces this schema at
generation time. If the output cannot be parsed into this schema, the gateway
treats it as an LLM-unavailable event (spec §4.3).

Spec references:
  §4.2  — LLM output contract (exact schema reproduced here)
  §4.3  — Schema failure → treat as LLM unavailable
  N6    — No applicant PII; only name pair + category + legal form sent
"""
from typing import Any, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class ParseOutput(BaseModel):
    """
    Stage ① parse result returned by the LLM for cross-validation.
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    core_ar: str = Field(description="Core Arabic name without legal-form or branch tokens")
    core_en: str = Field(description="Core English name without legal-form or branch tokens")
    activity_words: list[str] = Field(default_factory=list, description="Activity descriptors extracted from the name")
    legal_form: Optional[str] = Field(default=None, description="Legal form token detected, or null")
    branch: bool = Field(default=False, description="True if a branch suffix was detected")


class TransliterationOutput(BaseModel):
    """
    Transliteration consistency check output (F7).
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    consistent: bool = Field(default=True, description="True if Arabic and English are consistent transliterations")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score [0.0, 1.0]")
    expected_en: str = Field(default="", description="Expected English transliteration of the Arabic name")
    expected_ar: str = Field(default="", description="Expected Arabic transliteration of the English name")


class RiskOutput(BaseModel):
    """
    A single identified risk/flag in the trade name (spec §4.2).
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    category: Literal[
        "prohibited", "profanity", "unfriendly", "special",
        "divine_name", "location", "family_name",
        "impersonation", "misleading",
    ] = Field(
        validation_alias=AliasChoices("category", "type", "risk_type"),
        description="Risk category",
    )
    language: Literal["ar", "en", "both"] = Field(
        default="both",
        description="Which language component carries the risk",
    )
    span: str = Field(default="", description="The specific word/span that triggered this risk")
    severity: Literal["block", "review", "info"] = Field(
        default="review",
        description="Risk severity level: block | review | info",
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score [0.0, 1.0]")
    reason_en: str = Field(default="", description="Bilingual explanation — English")
    reason_ar: str = Field(default="", description="Bilingual explanation — Arabic")
    fix_en: str = Field(default="", description="Actionable fix suggestion — English")
    fix_ar: str = Field(default="", description="Actionable fix suggestion — Arabic")


class SimilarityJudgement(BaseModel):
    """
    LLM judgment on whether a retrieved similar name is confusingly similar
    to the submitted name (Stage ④, F3 semantic layer).
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    registry_id: int = Field(description="trade_name_id from TradeNameIndex")
    confusingly_similar: bool = Field(default=False, description="True if the names are confusingly similar semantically")
    reason_en: str = Field(default="", description="Reason for the judgement — English")
    reason_ar: str = Field(default="", description="Reason for the judgement — Arabic")


class ActivityFitOutput(BaseModel):
    """
    Whether the trade name is appropriate for the declared activity category.
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    fits: bool = Field(
        default=True,
        validation_alias=AliasChoices("fits", "is_appropriate", "appropriate", "isAppropriate"),
        description="True if the name is appropriate for the activity category",
    )
    suggested_category_code: Optional[str] = Field(
        default=None,
        description="Suggested category code when fits=False, or null"
    )
    reason_en: str = Field(default="", description="Reason for fit verdict — English")
    reason_ar: str = Field(default="", description="Reason for fit verdict — Arabic")


# ---------------------------------------------------------------------------
# Root output model
# ---------------------------------------------------------------------------

class LlmAnalyzerOutput(BaseModel):
    """
    Complete LLM Analyzer output (spec §4.2).
    """
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    parse: ParseOutput = Field(
        validation_alias=AliasChoices("parse", "parsed_name", "parsedName"),
    )
    transliteration: TransliterationOutput = Field(
        validation_alias=AliasChoices("transliteration", "transliteration_check", "transliterationCheck"),
    )
    risks: list[RiskOutput] = Field(default_factory=list)
    similar: list[SimilarityJudgement] = Field(default_factory=list)
    activity_fit: ActivityFitOutput = Field(
        validation_alias=AliasChoices("activity_fit", "activityFit", "activity_suitability", "suitability"),
    )

    @field_validator("risks", mode="before")
    @classmethod
    def _coerce_risks(cls, v: Any) -> list:
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            result = []
            for cat, details in v.items():
                if isinstance(details, dict):
                    if details.get("flagged") or details.get("severity") in ("block", "review", "medium", "high", "info"):
                        sev = "block" if details.get("severity") in ("block", "high") else ("info" if details.get("severity") == "info" else "review")
                        result.append({
                            "category": cat,
                            "severity": sev,
                            "reason_en": details.get("reason_en", details.get("reason", "")),
                            "reason_ar": details.get("reason_ar", details.get("reason", "")),
                            "span": details.get("span", ""),
                            "language": details.get("language", "both"),
                            "fix_en": details.get("fix_en", details.get("fix", "")),
                            "fix_ar": details.get("fix_ar", details.get("fix", "")),
                        })
                elif isinstance(details, bool) and details:
                    result.append({"category": cat, "severity": "review"})
            return result
        return []

    @field_validator("similar", mode="before")
    @classmethod
    def _coerce_similar(cls, v: Any) -> list:
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            result = []
            for reg_id, item in v.items():
                if isinstance(item, dict):
                    try:
                        rid = int(reg_id)
                    except Exception:
                        rid = item.get("registry_id", 0)
                    result.append({
                        "registry_id": rid,
                        "confusingly_similar": bool(item.get("confusingly_similar", item.get("similar", False))),
                        "reason_en": item.get("reason_en", ""),
                        "reason_ar": item.get("reason_ar", ""),
                    })
            return result
        return []


# ---------------------------------------------------------------------------
# Phase 3 schemas: Suggestions, Transliteration, Category
# ---------------------------------------------------------------------------

class SuggestionCandidate(BaseModel):
    """A single bilingual trade name suggestion candidate (F8, F9)."""
    name_ar: str = Field(..., description="Arabic suggestion")
    name_en: str = Field(..., description="English suggestion (will be uppercased per F17)")
    reason_en: Optional[str] = Field(default="", description="Why this suggestion works (English)")
    reason_ar: Optional[str] = Field(default="", description="Why this suggestion works (Arabic)")


class SuggestionBatchOutput(BaseModel):
    """Output schema for Stage ⑥ LLM suggestion generation."""
    suggestions: list[SuggestionCandidate] = Field(
        default_factory=list,
        description="List of ~25 drafted bilingual suggestions",
    )


class TransliterationCheckOutput(BaseModel):
    """Output schema for Phase 3.2 transliteration validation (F7)."""
    consistent: bool = Field(..., description="True if Arabic and English are consistent transliterations")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0.0, 1.0]")
    expected_en: str = Field(..., description="Expected English transliteration")
    expected_ar: str = Field(..., description="Expected Arabic transliteration")
    reason_en: Optional[str] = Field(default="", description="Bilingual explanation (English)")
    reason_ar: Optional[str] = Field(default="", description="Bilingual explanation (Arabic)")


class CategorySuggestionOutput(BaseModel):
    """Output schema for Phase 3.3 activity category suggestion (E6)."""
    suggested_category_code: Optional[str] = Field(
        default=None,
        description="Suggested activity category code, or null if ambiguous",
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score [0.0, 1.0]")
    reason_en: str = Field(..., description="Explanation in English")
    reason_ar: str = Field(..., description="Explanation in Arabic")


class ReviewerBriefOutput(BaseModel):
    """Output schema for Stage ⑧ Reviewer Copilot Brief (E5)."""
    recommendation: Literal["approve", "reject", "return", "ssp_committee"] = Field(
        ...,
        description="Recommended action: approve | reject | return | ssp_committee",
    )
    draft_admin_comments_en: str = Field(..., description="Draft DED admin comments in English")
    draft_admin_comments_ar: str = Field(..., description="Draft DED admin comments in Arabic")
    summary_en: Optional[str] = Field(default="", description="Executive summary in English")
    summary_ar: Optional[str] = Field(default="", description="Executive summary in Arabic")


# ---------------------------------------------------------------------------
# Phase 5 schemas: Lexicon Variant Proposals (Stage ⑨, E7)
# ---------------------------------------------------------------------------

class LexiconVariantsOutput(BaseModel):
    """Output schema for Stage ⑨ LLM lexicon variant proposals (E7)."""
    term: str = Field(..., description="Root term")
    variants: list[str] = Field(
        default_factory=list,
        description="List of proposed phonetic, spelling, and Arabizi variants",
    )
    reasoning: Optional[str] = Field(
        default="",
        description="Reasoning or linguistic rationale for proposed variants",
    )


