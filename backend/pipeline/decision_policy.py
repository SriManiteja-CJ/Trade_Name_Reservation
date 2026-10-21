"""
pipeline/decision_policy.py
Stage ⑤ — Decision Policy

Combines all signals from Stages ②, ③, ④ into one final outcome:
  OK | NEEDS_REVIEW | BLOCKED

This module is PURELY DETERMINISTIC. The LLM CANNOT override it.
A hard gate (exact duplicate, lexicon block) always produces BLOCKED regardless
of what the LLM says.

Decision rules (spec §4.1):
  ┌────────────────────────────────────────────────────────┬──────────────────┐
  │ Signal                                                  │ Outcome          │
  ├────────────────────────────────────────────────────────┼──────────────────┤
  │ Hard gate hit (exact duplicate, lexicon block)          │ BLOCKED          │
  │ LLM risk severity=block AND confidence ≥ threshold      │ BLOCKED          │
  │ LLM risk=review OR low confidence OR transliteration    │ NEEDS_REVIEW     │
  │   mismatch OR poor activity fit                         │                  │
  │ LLM unavailable or timed out                            │ NEEDS_REVIEW     │
  │   (hard gates still ran; best outcome is NEEDS_REVIEW)  │ (not OK)         │
  │ No flags                                                │ OK               │
  └────────────────────────────────────────────────────────┴──────────────────┘

Additional rules:
  F12: If skip_word_checks=True, word-check signals from Stage ② are discarded
       from the BLOCKED/NEEDS_REVIEW decision (similarity is kept).
  F14: The failing language is selected based on the lang header; all reasons
       are always returned in BOTH languages.
  N1:  LLM unavailable → best outcome is NEEDS_REVIEW, never OK.

Spec references:
  §4.1 — decision rules table (implemented exactly as written)
  F12   — skip_word_checks exemption applied here
  F14   — lang header determines primary message language
  N1    — fail closed: LLM outage never approves
  N4    — every flag explained in AR + EN
  N9    — legacy boolean fields mapped from LLM categories
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from config.settings import FlagMode, get_settings
from pipeline.deterministic_gates import GateSignal, SignalType

settings = get_settings()


class Outcome(str, Enum):
    OK = "OK"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"


@dataclass
class ReasonEntry:
    """
    A single bilingual reason+fix entry in the validation response.
    Maps to spec §4.2 RiskOutput fields and N4 (bilingual explanations).
    """
    category: str          # e.g. "exact_duplicate", "prohibited", "profanity" …
    severity: str          # "block" | "review" | "info"
    language: str          # "ar" | "en" | "both"
    reason_en: str
    reason_ar: str
    fix_en: str
    fix_ar: str
    source: str = "deterministic"  # "deterministic" | "llm"
    confidence: float = 1.0


@dataclass
class PolicyResult:
    """
    The final output of Stage ⑤.

    Fields:
      outcome:           OK | NEEDS_REVIEW | BLOCKED
      reasons:           Bilingual list of all flags  (N4)
      legacy_flags:      Dict of legacy boolean fields (N9 backward compat)
      similarity_score:  Highest similarity score from Stage ③ (for Similarity field)
      llm_was_available: False when the LLM timed out or returned invalid output
      primary_lang:      "ar" | "en" — which lang the response message should use (F14)
    """
    outcome: Outcome
    reasons: list[ReasonEntry] = field(default_factory=list)
    legacy_flags: dict[str, bool] = field(default_factory=dict)
    similarity_score: float = 0.0
    llm_was_available: bool = True
    primary_lang: str = "en"


# Legacy field names (N9) — initialized to False, set True when relevant signals found
_DEFAULT_LEGACY_FLAGS: dict[str, bool] = {
    "Prohibted": False,
    "Profanity": False,
    "Unfriendly": False,
    "Special": False,
    "AllahNames": False,
    "LocationNames": False,
    "FamilyNames": False,
    "Similarity": False,
}

# Mapping from F4 category → legacy field name
_CATEGORY_TO_LEGACY: dict[str, str] = {
    "prohibited": "Prohibted",
    "profanity": "Profanity",
    "unfriendly": "Unfriendly",
    "special": "Special",
    "divine_name": "AllahNames",
    "location": "LocationNames",
    "family_name": "FamilyNames",
}


def apply_policy(
    gate_signals: list[GateSignal],
    llm_output=None,            # LlmAnalyzerOutput | None (None = LLM unavailable)
    skip_word_checks: bool = False,
    lang_header: str = "en",
    similarity_score: float = 0.0,
) -> PolicyResult:
    """
    Apply the decision policy and produce the final PolicyResult.

    Args:
        gate_signals:      Signals from Stage ② (deterministic gates)
        llm_output:        Parsed LLM output from Stage ④, or None if unavailable
        skip_word_checks:  F12 exemption flag from NameComposer
        lang_header:       Accept-Language / lang header value ("ar" or "en")
        similarity_score:  Highest similarity score from Stage ③ retriever

    Returns:
        PolicyResult with the final outcome and all bilingual reasons.
    """
    reasons: list[ReasonEntry] = []
    legacy_flags = dict(_DEFAULT_LEGACY_FLAGS)
    llm_available = llm_output is not None

    # -----------------------------------------------------------------------
    # Step 1: Process Stage ② gate signals
    # Apply F12 exemption: if skip_word_checks, drop lexicon signals from
    # the decision (but keep exact_duplicate signals — see Ambiguity #2).
    # -----------------------------------------------------------------------
    has_hard_block = False
    has_review_flag = False

    for sig in gate_signals:
        # F12: skip word-check (lexicon) signals only
        if skip_word_checks and sig.source == "lexicon":
            continue

        # Collect the reason
        reasons.append(
            ReasonEntry(
                category=sig.category or sig.source,
                severity=sig.severity or "block",
                language="both",
                reason_en=sig.reason_en,
                reason_ar=sig.reason_ar,
                fix_en=sig.fix_en,
                fix_ar=sig.fix_ar,
                source="deterministic",
                confidence=1.0,
            )
        )

        # Update legacy flags (N9)
        if sig.category and sig.category in _CATEGORY_TO_LEGACY:
            legacy_flags[_CATEGORY_TO_LEGACY[sig.category]] = True

        if sig.signal_type == SignalType.BLOCKED:
            has_hard_block = True
        elif sig.signal_type == SignalType.NEEDS_REVIEW:
            has_review_flag = True

    # -----------------------------------------------------------------------
    # Step 2: Process LLM output (Stage ④)
    # The LLM can ADD flags (BLOCKED or NEEDS_REVIEW) but NEVER lift a hard block.
    # -----------------------------------------------------------------------
    block_threshold = settings.policy_block_confidence_threshold
    review_threshold = settings.policy_review_confidence_threshold

    if llm_output is not None:
        # 2a. Process risks
        for risk in (llm_output.risks or []):
            cat = risk.category
            sev = risk.severity
            conf = risk.confidence

            if sev == "block" and conf >= block_threshold:
                has_hard_block = True   # LLM block-level risk at high confidence
                effective_severity = "block"
            elif sev == "block" and conf < block_threshold:
                has_review_flag = True  # low confidence block → review
                effective_severity = "review"
            elif sev == "review":
                has_review_flag = True
                effective_severity = "review"
            else:
                effective_severity = "info"

            reasons.append(
                ReasonEntry(
                    category=cat,
                    severity=effective_severity,
                    language=risk.language,
                    reason_en=risk.reason_en,
                    reason_ar=risk.reason_ar,
                    fix_en=risk.fix_en,
                    fix_ar=risk.fix_ar,
                    source="llm",
                    confidence=conf,
                )
            )

            # Update legacy flags
            if cat in _CATEGORY_TO_LEGACY:
                legacy_flags[_CATEGORY_TO_LEGACY[cat]] = True

        # 2b. Transliteration mismatch → NEEDS_REVIEW (spec §4.1)
        if (
            hasattr(llm_output, "transliteration")
            and llm_output.transliteration
            and not llm_output.transliteration.consistent
        ):
            has_review_flag = True
            reasons.append(
                ReasonEntry(
                    category="transliteration_mismatch",
                    severity="review",
                    language="both",
                    reason_en=(
                        "The Arabic and English names do not appear to be consistent "
                        f"transliterations of each other. "
                        f"Expected English: {llm_output.transliteration.expected_en}, "
                        f"Expected Arabic: {llm_output.transliteration.expected_ar}."
                    ),
                    reason_ar=(
                        "الاسم العربي والإنجليزي لا يبدوان ترجمة صوتية متسقة لبعضهما البعض. "
                        f"الإنجليزية المتوقعة: {llm_output.transliteration.expected_en}، "
                        f"العربية المتوقعة: {llm_output.transliteration.expected_ar}."
                    ),
                    fix_en=(
                        f"Consider using '{llm_output.transliteration.expected_en}' "
                        f"as the English form."
                    ),
                    fix_ar=(
                        f"يُقترح استخدام '{llm_output.transliteration.expected_ar}' "
                        f"كالصيغة العربية."
                    ),
                    source="llm",
                    confidence=llm_output.transliteration.confidence,
                )
            )

        # 2c. Poor activity fit → NEEDS_REVIEW (spec §4.1)
        if (
            hasattr(llm_output, "activity_fit")
            and llm_output.activity_fit
            and not llm_output.activity_fit.fits
        ):
            has_review_flag = True
            reasons.append(
                ReasonEntry(
                    category="activity_fit",
                    severity="review",
                    language="both",
                    reason_en=llm_output.activity_fit.reason_en,
                    reason_ar=llm_output.activity_fit.reason_ar,
                    fix_en=(
                        f"Consider activity category "
                        f"{llm_output.activity_fit.suggested_category_code or 'not specified'}."
                    ),
                    fix_ar=(
                        f"يُقترح فئة نشاط: "
                        f"{llm_output.activity_fit.suggested_category_code or 'غير محدد'}."
                    ),
                    source="llm",
                    confidence=1.0,
                )
            )

    else:
        # -----------------------------------------------------------------------
        # N1 — LLM outage: when ai_analyzer is enabled (on or shadow), but the LLM
        # was unavailable or timed out, best outcome is NEEDS_REVIEW, never OK.
        # When ai_analyzer is 'off' (Phase 1 / deterministic mode), absence of LLM
        # is intentional configuration, so clean deterministic gates produce OK.
        # -----------------------------------------------------------------------
        current_ai_flag = get_settings().ai_analyzer
        if current_ai_flag != FlagMode.off:
            if not has_hard_block:
                has_review_flag = True

    # -----------------------------------------------------------------------
    # Step 3: Determine final outcome
    # Hard blocks (from gates OR high-confidence LLM) are never overridden.
    # -----------------------------------------------------------------------
    if has_hard_block:
        outcome = Outcome.BLOCKED
    elif has_review_flag:
        outcome = Outcome.NEEDS_REVIEW
    else:
        outcome = Outcome.OK

    # -----------------------------------------------------------------------
    # Similarity score for legacy Similarity field
    # -----------------------------------------------------------------------
    legacy_flags["Similarity"] = similarity_score > 0.5

    # -----------------------------------------------------------------------
    # F14 — primary language for the failing message
    # All reasons are always bilingual; primary_lang controls the main message.
    # -----------------------------------------------------------------------
    primary_lang = lang_header if lang_header in ("ar", "en") else "en"

    return PolicyResult(
        outcome=outcome,
        reasons=reasons,
        legacy_flags=legacy_flags,
        similarity_score=similarity_score,
        llm_was_available=llm_available,
        primary_lang=primary_lang,
    )


def check_feature_flag_allows_llm() -> bool:
    """
    Return True if the Ai.Analyzer flag is 'on' (LLM result affects outcome).
    Return False if 'off' or 'shadow' (shadow: LLM runs but result is logged only).
    """
    return settings.ai_analyzer == FlagMode.on


def is_shadow_mode() -> bool:
    """Return True if Ai.Analyzer is in shadow mode."""
    return settings.ai_analyzer == FlagMode.shadow
