"""
pipeline/name_composer.py
NameComposer — applies branch suffix, legal-form token swap, and F12 exemption.

Spec references:
  F10 — Outside-UAQ branches get suffix "Umm Al Quwain Branch" / "فرع أم القيوين";
         conflicts checked WITH the suffix included.
  F11 — Legal-form amendment swaps or removes the old legal-form wording in both
         languages, then checks conflicts.
  F12 — If the name is unchanged and only legal form or branch status changes,
         skip word checks (F4 lexicon checks) but keep the similarity check (F3).
         This flag is set here and consumed by Stage ⑤ decision policy.
  F8  — Legal form shown in suggestion output when the legal form requires it
         (list of legal forms requiring display is in settings/config).
"""
from dataclasses import dataclass
from typing import Optional

from pipeline.normalizer import (
    NormalizedPair,
    normalize_arabic,
    normalize_english,
    strip_tokens,
)

# ---------------------------------------------------------------------------
# Legal forms that REQUIRE display in suggestion output (F8).
# Gap #2: complete list from DED needed. Placeholder common forms.
# ---------------------------------------------------------------------------
_LEGAL_FORMS_REQUIRING_DISPLAY: set[str] = {
    "llc",
    "l.l.c",
    "pjsc",
    "p.j.s.c",
    "ذ.م.م",
    "ش.م.ع",
}

# Branch suffix strings — authoritative from spec F10
BRANCH_SUFFIX_EN = "Umm Al Quwain Branch"
BRANCH_SUFFIX_AR = "فرع أم القيوين"


@dataclass
class ComposedName:
    """
    Result of NameComposer processing.

    Fields:
      effective_ar          — Arabic name to use for gate checks (with suffix/swap applied)
      effective_en          — English name to use for gate checks
      normalized_ar         — normalized form of effective_ar
      normalized_en         — normalized form of effective_en
      legal_form_token      — detected or amended legal form token (or None)
      branch                — True when name is for a branch outside UAQ (F10)
      skip_word_checks      — True when F12 exemption applies (skip F4 word checks)
      show_legal_form       — True when legal form must appear in suggestions (F8)
      original_normalized   — NormalizedPair of the original unchanged name
                              (used for F2 exclude-current-record logic)
    """
    effective_ar: str
    effective_en: str
    normalized_ar: str
    normalized_en: str
    legal_form_token: Optional[str]
    branch: bool
    skip_word_checks: bool
    show_legal_form: bool
    original_normalized: NormalizedPair


def compose(
    name_ar: str,
    name_en: str,
    operation_type: str,        # new | edit | renew | branch | legal_form_amend
    is_outside_uaq: bool = False,
    old_legal_form: Optional[str] = None,
    new_legal_form: Optional[str] = None,
    previous_name_ar: Optional[str] = None,  # for F12: unchanged-name detection
    previous_name_en: Optional[str] = None,
) -> ComposedName:
    """
    Apply branch suffix (F10), legal-form swap (F11), and determine the F12
    skip_word_checks flag.

    Returns a ComposedName with the effective names to be used in Stage ②
    (deterministic gates) and Stage ③ (retriever).

    Args:
        name_ar:           Submitted Arabic trade name (raw input)
        name_en:           Submitted English trade name (raw input)
        operation_type:    One of: new | edit | renew | branch | legal_form_amend
        is_outside_uaq:    True when branch is outside UAQ (triggers F10 suffix)
        old_legal_form:    Previous legal-form token (for F11 swap)
        new_legal_form:    New legal-form token (for F11 swap)
        previous_name_ar:  Raw AR name before edit/renew (for F12 detection)
        previous_name_en:  Raw EN name before edit/renew (for F12 detection)
    """
    # Step 1 — normalize the submitted name
    norm_ar = normalize_arabic(name_ar)
    norm_en = normalize_english(name_en)
    original_normalized = NormalizedPair(
        normalized_ar=norm_ar,
        normalized_en=norm_en,
        raw_ar=name_ar,
        raw_en=name_en,
    )

    effective_ar = name_ar
    effective_en = name_en
    branch = False
    skip_word_checks = False

    # -----------------------------------------------------------------------
    # F12 — skip_word_checks detection
    # If the name itself has NOT changed and only legal form or branch status
    # changes, set skip_word_checks = True. Similarity check is still performed.
    # -----------------------------------------------------------------------
    if operation_type in ("edit", "renew", "legal_form_amend") and (
        previous_name_ar is not None and previous_name_en is not None
    ):
        prev_norm_ar = normalize_arabic(previous_name_ar)
        prev_norm_en = normalize_english(previous_name_en)
        # Strip legal-form tokens before comparing cores
        prev_parsed_ar = strip_tokens(prev_norm_ar, "ar")
        prev_parsed_en = strip_tokens(prev_norm_en, "en")
        curr_parsed_ar = strip_tokens(norm_ar, "ar")
        curr_parsed_en = strip_tokens(norm_en, "en")

        name_unchanged = (
            prev_parsed_ar.core == curr_parsed_ar.core
            and prev_parsed_en.core == curr_parsed_en.core
        )
        only_form_changed = (
            operation_type == "legal_form_amend"
            or (old_legal_form != new_legal_form)
        )

        if name_unchanged and only_form_changed:
            skip_word_checks = True

    # -----------------------------------------------------------------------
    # F11 — Legal-form amendment: swap or remove old legal-form wording
    # The modified name is then checked for conflicts in Stage ②.
    # -----------------------------------------------------------------------
    if operation_type == "legal_form_amend" and old_legal_form is not None:
        _LF_EN_TO_AR = {
            "llc": "ذ.م.م",
            "l.l.c": "ذ.م.م",
            "limited liability company": "ذات مسؤولية محدودة",
            "pjsc": "ش.م.ع",
            "public joint stock company": "شركة مساهمة عامة",
            "psc": "ش.م.خ",
            "private shareholding company": "شركة مساهمة خاصة",
            "sole proprietorship": "مؤسسة فردية",
            "sole establishment": "مؤسسة فردية",
            "civil company": "شركة مدنية",
        }
        _LF_AR_TO_EN = {
            "ذ.م.م": "LLC",
            "ذات مسئوليه محدوده": "Limited Liability Company",
            "ذات مسؤولية محدودة": "Limited Liability Company",
            "ش.م.ع": "PJSC",
            "شركه مساهمه عامه": "Public Joint Stock Company",
            "شركة مساهمة عامة": "Public Joint Stock Company",
            "ش.م.خ": "PSC",
            "شركه مساهمه خاصه": "Private Shareholding Company",
            "شركة مساهمة خاصة": "Private Shareholding Company",
            "مؤسسه فرديه": "Sole Proprietorship",
            "مؤسسة فردية": "Sole Proprietorship",
            "شركه مدنيه": "Civil Company",
            "شركة مدنية": "Civil Company",
        }

        # Remove old legal-form token from both names
        if old_legal_form:
            old_lf_lower = old_legal_form.strip().lower()
            old_ar = _LF_EN_TO_AR.get(old_lf_lower, old_legal_form)
            old_en = _LF_AR_TO_EN.get(old_legal_form.strip(), old_legal_form)
            effective_ar = effective_ar.replace(old_ar, "").replace(old_legal_form, "").strip()
            effective_en = effective_en.replace(old_en, "").replace(old_legal_form, "").strip()

        # Append new legal form in respective language if provided
        if new_legal_form:
            new_lf_lower = new_legal_form.strip().lower()
            new_ar = _LF_EN_TO_AR.get(new_lf_lower, new_legal_form)
            new_en = _LF_AR_TO_EN.get(new_legal_form.strip(), new_legal_form)
            effective_ar = f"{effective_ar} {new_ar}".strip()
            effective_en = f"{effective_en} {new_en}".strip()

    # -----------------------------------------------------------------------
    # F10 — Outside-UAQ branch: append suffix BEFORE gate checks
    # The conflicts MUST be checked with the suffix included.
    # -----------------------------------------------------------------------
    if operation_type == "branch" and is_outside_uaq:
        effective_ar = f"{effective_ar} {BRANCH_SUFFIX_AR}"
        effective_en = f"{effective_en} {BRANCH_SUFFIX_EN}"
        branch = True

    # Normalize the effective names (post F10/F11 modifications)
    eff_norm_ar = normalize_arabic(effective_ar)
    eff_norm_en = normalize_english(effective_en)

    # Detect legal form for display (F8)
    parsed_en = strip_tokens(eff_norm_en, "en")
    lf_token = parsed_en.legal_form_token
    show_legal_form = (lf_token is not None and lf_token in _LEGAL_FORMS_REQUIRING_DISPLAY)

    return ComposedName(
        effective_ar=effective_ar,
        effective_en=effective_en,
        normalized_ar=eff_norm_ar,
        normalized_en=eff_norm_en,
        legal_form_token=lf_token,
        branch=branch,
        skip_word_checks=skip_word_checks,
        show_legal_form=show_legal_form,
        original_normalized=original_normalized,
    )
