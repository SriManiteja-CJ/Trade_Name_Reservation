"""
pipeline/normalizer.py
Stage ① — Normalizer

Implements ALL normalization rules specified in spec §3, Component ①:

Arabic normalization:
  - Remove diacritics (harakat: U+064B–U+065F, U+0610–U+061A, U+06D6–U+06DC, U+06DF–U+06E4, U+06E7–U+06ED)
  - Remove tatweel / kashida (U+0640)
  - Unify alef forms: أ (U+0623) إ (U+0625) آ (U+0622) أ → ا (U+0627)
  - Normalize ة (ta marbuta, U+0629) → ه (U+0647)
  - Normalize ى (alef maqsura, U+0649) → ي (U+064A)
  - Apply NFKC Unicode normalization

English normalization:
  - NFKC Unicode normalization
  - Case-fold to lowercase (comparison only; F17 upper-case applied at output layer)
  - Strip leading/trailing whitespace; collapse internal whitespace

Token stripping (F5, F10, F11):
  - Strip legal-form tokens by exact match (spec says "exact match")
  - Strip branch tokens: "Umm Al Quwain Branch" / "فرع أم القيوين"
  - Produces: core_name, activity_words (placeholder list), legal_form token, branch bool

Spec requirement cross-reference:
  F1  — both Arabic and English forms are normalized
  F2  — normalized keys used for exact duplicate check
  F5  — parse output: core name, activity words, legal form
  F10 — branch token recognized and stripped
  F11 — legal-form tokens recognized and stripped
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Arabic Unicode ranges for diacritic removal
# ---------------------------------------------------------------------------
# Harakat (short vowel marks and related diacritics)
_ARABIC_DIACRITICS_RE = re.compile(
    r"[\u064B-\u065F"   # Fathatan–Sukun range
    r"\u0610-\u061A"   # Arabic sign range
    r"\u06D6-\u06DC"   # Arabic small high ranges
    r"\u06DF-\u06E4"
    r"\u06E7-\u06ED"
    r"\u0670"          # Arabic letter superscript alef
    r"]"
)

# Tatweel / kashida U+0640
_TATWEEL = "\u0640"

# Alef unification map: all alef variants → bare alef ا (U+0627)
_ALEF_VARIANTS = str.maketrans({
    "\u0623": "\u0627",  # أ ARABIC LETTER ALEF WITH HAMZA ABOVE
    "\u0625": "\u0627",  # إ ARABIC LETTER ALEF WITH HAMZA BELOW
    "\u0622": "\u0627",  # آ ARABIC LETTER ALEF WITH MADDA ABOVE
    "\u0671": "\u0627",  # ٱ ARABIC LETTER ALEF WASLA
    "\u0672": "\u0627",  # ٲ
    "\u0673": "\u0627",  # ٳ
})

# ة → ه
_TA_MARBUTA_MAP = str.maketrans({"\u0629": "\u0647"})

# ى → ي
_ALEF_MAQSURA_MAP = str.maketrans({"\u0649": "\u064A"})

# ---------------------------------------------------------------------------
# Whitespace normalizer (collapse multiple spaces)
# ---------------------------------------------------------------------------
_WHITESPACE_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Legal-form token lists (Gap #2: complete list TBD from DED)
# Placeholder entries based on common UAE legal forms; DED must supply full list.
# Stripping is by EXACT match of normalized token at word boundaries.
# ---------------------------------------------------------------------------
# English legal-form tokens (normalized / lowercased)
_LEGAL_FORM_TOKENS_EN: list[str] = [
    "llc",
    "l.l.c",
    "llc.",
    "limited liability company",
    "pjsc",
    "p.j.s.c",
    "public joint stock company",
    "psc",
    "private shareholding company",
    "fz llc",
    "fz-llc",
    "freezone llc",
    "sole proprietorship",
    "sole establishment",
    "civil company",
]

# Arabic legal-form tokens (normalized — diacritics and tatweel removed)
_LEGAL_FORM_TOKENS_AR: list[str] = [
    "ذ.م.م",
    "ذات مسئوليه محدوده",
    "ذات مسئولية محدودة",
    "ش.م.ع",
    "شركه مساهمه عامه",
    "شركة مساهمة عامة",
    "ش.م.خ",
    "شركه مساهمه خاصه",
    "شركة مساهمة خاصة",
    "م.ف",
    "مؤسسه فرديه",
    "مؤسسة فردية",
    "شركه مدنيه",
    "شركة مدنية",
]

# Branch tokens — EXACT strings used in F10 and F11
# English: normalized/lowercased form
_BRANCH_TOKEN_EN: str = "umm al quwain branch"
# Arabic: normalized form (after our Arabic normalization pipeline)
_BRANCH_TOKEN_AR: str = "فرع ام القوين"  # normalized form of "فرع أم القيوين"


# ---------------------------------------------------------------------------
# Data classes returned by the normalizer
# ---------------------------------------------------------------------------
@dataclass
class NormalizedPair:
    """Normalized AR and EN forms for a name pair."""
    normalized_ar: str
    normalized_en: str
    raw_ar: str
    raw_en: str


@dataclass
class ParsedName:
    """
    Result of stripping legal-form and branch tokens from a normalized name.
    Implements F5 parse output (core name, activity words, legal form).
    F10 branch detection.
    F11 legal-form token identification.
    """
    core: str                           # normalized name with tokens stripped
    legal_form_token: Optional[str]     # matched legal-form token or None
    branch: bool                        # True when branch token found (F10)
    activity_words: list[str] = field(default_factory=list)
    # Note: activity_words decomposition requires domain knowledge (Gap #1);
    # the LLM parse (Stage ④) produces the authoritative split.
    # Here we return the core string as a single-element list as a placeholder.

    @property
    def core_name(self) -> str:
        return self.core

    @property
    def legal_form(self) -> Optional[str]:
        return self.legal_form_token


# ---------------------------------------------------------------------------
# Core normalization functions
# ---------------------------------------------------------------------------

def normalize_arabic(text: str) -> str:
    """
    Apply the full Arabic normalization pipeline from spec §3 Component ①:
      1. NFKC Unicode normalization
      2. Remove diacritics (harakat)
      3. Remove tatweel (U+0640)
      4. Unify alef forms → ا
      5. ة → ه
      6. ى → ي
      7. Collapse whitespace
    """
    # Step 1: NFKC
    text = unicodedata.normalize("NFKC", text)
    # Step 2: remove diacritics
    text = _ARABIC_DIACRITICS_RE.sub("", text)
    # Step 3: remove tatweel
    text = text.replace(_TATWEEL, "")
    # Step 4: unify alef variants
    text = text.translate(_ALEF_VARIANTS)
    # Step 5: ة → ه
    text = text.translate(_TA_MARBUTA_MAP)
    # Step 6: ى → ي
    text = text.translate(_ALEF_MAQSURA_MAP)
    # Step 7: collapse whitespace
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def normalize_english(text: str) -> str:
    """
    Apply English normalization from spec §3 Component ①:
      1. NFKC Unicode normalization
      2. Case-fold (lowercase) — NOTE: F17 requires UPPERCASE in suggestion output;
         that transformation is applied at the output layer, NOT here.
      3. Collapse whitespace
    """
    # Step 1: NFKC
    text = unicodedata.normalize("NFKC", text)
    # Step 2: case-fold
    text = text.casefold()
    # Step 3: collapse whitespace
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def normalize_pair(ar: str, en: str) -> NormalizedPair:
    """
    Normalize both forms of a trade-name pair.
    Satisfies F1 (both Arabic and English forms processed).
    """
    return NormalizedPair(
        normalized_ar=normalize_arabic(ar),
        normalized_en=normalize_english(en),
        raw_ar=ar,
        raw_en=en,
    )


def _strip_legal_form_en(text: str) -> tuple[str, Optional[str]]:
    """
    Strip a legal-form token from the normalized English name by exact word-boundary match.
    Returns (stripped_text, matched_token_or_None).
    Spec says "exact match" — we match tokens at word boundaries.
    """
    for token in sorted(_LEGAL_FORM_TOKENS_EN, key=len, reverse=True):
        # Build a word-boundary aware pattern
        pattern = r"(?<!\w)" + re.escape(token) + r"(?!\w)"
        if re.search(pattern, text):
            stripped = re.sub(pattern, "", text).strip()
            stripped = _WHITESPACE_RE.sub(" ", stripped).strip()
            return stripped, token
    return text, None


def _strip_legal_form_ar(text: str) -> tuple[str, Optional[str]]:
    """
    Strip a legal-form token from the normalized Arabic name by exact match.
    Returns (stripped_text, matched_token_or_None).
    """
    for token in sorted(_LEGAL_FORM_TOKENS_AR, key=len, reverse=True):
        if token in text:
            stripped = text.replace(token, "").strip()
            stripped = _WHITESPACE_RE.sub(" ", stripped).strip()
            return stripped, token
    return text, None


def strip_tokens(normalized_text: str, lang: str) -> ParsedName:
    """
    Strip legal-form and branch tokens from a normalized name.

    Args:
        normalized_text: Output from normalize_arabic() or normalize_english()
        lang: "ar" or "en"

    Returns:
        ParsedName with:
          - core: name with tokens removed
          - legal_form_token: the matched legal-form token (or None)
          - branch: True if branch token was found (F10)
          - activity_words: placeholder (authoritative split comes from Stage ④)

    Spec references: F5 (parse), F10 (branch), F11 (legal-form)
    """
    text = normalized_text
    branch = False

    # 1. Check and strip branch token (F10)
    if lang == "en":
        if _BRANCH_TOKEN_EN in text:
            text = text.replace(_BRANCH_TOKEN_EN, "").strip()
            text = _WHITESPACE_RE.sub(" ", text).strip()
            branch = True
        text, lf_token = _strip_legal_form_en(text)
    elif lang == "ar":
        # Normalize the branch token before comparison
        branch_norm = normalize_arabic("فرع أم القيوين")
        if branch_norm in text:
            text = text.replace(branch_norm, "").strip()
            text = _WHITESPACE_RE.sub(" ", text).strip()
            branch = True
        text, lf_token = _strip_legal_form_ar(text)
    else:
        lf_token = None

    return ParsedName(
        core=text,
        legal_form_token=lf_token,
        branch=branch,
        # Single placeholder word; LLM parse (Stage ④) provides the authoritative split
        activity_words=[text] if text else [],
    )


def is_normalized_idempotent(text: str, lang: str) -> bool:
    """
    Verify that applying normalization twice yields the same result.
    Used in tests to confirm idempotency.
    """
    if lang == "ar":
        return normalize_arabic(normalize_arabic(text)) == normalize_arabic(text)
    return normalize_english(normalize_english(text)) == normalize_english(text)
