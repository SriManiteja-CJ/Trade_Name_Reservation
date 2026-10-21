"""
tests/test_normalizer.py
Unit tests for Stage ① Normalizer (pipeline/normalizer.py).

Spec references:
  §3 Component ① — Arabic & English normalization rules, token stripping
  F1 — Arabic & English trade names normalized
  F5 — Token stripping produces core name, legal form token, branch bool
  F10 — Branch suffix recognized
  F11 — Legal form recognized
"""
import pytest
from pipeline.normalizer import (
    normalize_arabic,
    normalize_english,
    normalize_pair,
    strip_tokens,
)


def test_arabic_diacritics_removal():
    """Verify short vowels / harakat are completely removed."""
    vowelized = "مُحَمَّدٌ"
    assert normalize_arabic(vowelized) == "محمد"


def test_arabic_tatweel_removal():
    """Verify tatweel / kashida (U+0640) is stripped."""
    with_tatweel = "شـــركــة"
    # Note: ة also normalizes to ه
    assert normalize_arabic(with_tatweel) == "شركه"


def test_arabic_alef_unification():
    """Verify all alef forms unify to bare alef ا."""
    assert normalize_arabic("أحمد") == "احمد"
    assert normalize_arabic("إبراهيم") == "ابراهيم"
    assert normalize_arabic("آمنة") == "امنه"


def test_arabic_ta_marbuta_and_alef_maqsura():
    """Verify ة → ه and ى → ي."""
    assert normalize_arabic("مدينة") == "مدينه"
    assert normalize_arabic("هدى") == "هدي"
    assert normalize_arabic("مستشفى") == "مستشفي"


def test_arabic_normalization_idempotent():
    """Verify normalization is idempotent (f(f(x)) == f(x))."""
    sample = "مُؤَسَّسَــةُ الأَمَـلِ لِلتِّـجَارَةِ"
    first = normalize_arabic(sample)
    second = normalize_arabic(first)
    assert first == second


def test_english_normalization():
    """Verify NFKC normalization, lowercase folding, and whitespace collapsing."""
    raw = "  Acme   Trading  &  Consulting   LLC   "
    normalized = normalize_english(raw)
    assert normalized == "acme trading & consulting llc"


def test_normalize_pair():
    """Verify normalize_pair returns dataclass with both normalized forms."""
    pair = normalize_pair("شَـرِكَةُ النُّورِ", "  AL NOOR  TRADING  ")
    assert pair.normalized_ar == "شركه النور"
    assert pair.normalized_en == "al noor trading"


def test_strip_tokens_english_legal_form():
    """Verify legal-form token is stripped and recognized from English name."""
    parsed = strip_tokens("falcon general trading llc", lang="en")
    assert parsed.core_name == "falcon general trading"
    assert parsed.legal_form == "llc"
    assert parsed.branch is False


def test_strip_tokens_arabic_legal_form():
    """Verify legal-form token is stripped and recognized from Arabic name."""
    parsed = strip_tokens("مؤسسه الصقر للتجاره العامه ذ.م.م", lang="ar")
    assert "ذ.م.م" in parsed.legal_form or parsed.legal_form == "ذ.م.م"
    assert parsed.branch is False


def test_strip_tokens_english_branch():
    """Verify Umm Al Quwain Branch is recognized and stripped (F10)."""
    parsed = strip_tokens("star logistics umm al quwain branch", lang="en")
    assert parsed.core_name == "star logistics"
    assert parsed.branch is True


def test_strip_tokens_arabic_branch():
    """Verify فرع أم القيوين is recognized and stripped (F10)."""
    parsed = strip_tokens("شركه النجم اللوجستيه فرع ام القيوين", lang="ar")
    assert parsed.branch is True
    assert "فرع ام القيوين" not in parsed.core_name
