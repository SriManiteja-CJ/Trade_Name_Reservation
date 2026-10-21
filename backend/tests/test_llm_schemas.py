"""
tests/test_llm_schemas.py
Unit tests for llm/schemas.py — spec §4.2 LLM output contract.

Tests verify:
  - Valid full LlmAnalyzerOutput parses correctly
  - Partial / missing required fields are rejected
  - Literal constraints on category, severity, language enforce schema
  - Confidence is clamped [0.0, 1.0]
"""
import pytest
from pydantic import ValidationError

from llm.schemas import (
    ActivityFitOutput,
    LlmAnalyzerOutput,
    ParseOutput,
    RiskOutput,
    SimilarityJudgement,
    TransliterationOutput,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _valid_parse() -> dict:
    return {
        "core_ar": "نور",
        "core_en": "Nour",
        "activity_words": ["trading"],
        "legal_form": "LLC",
        "branch": False,
    }


def _valid_transliteration() -> dict:
    return {
        "consistent": True,
        "confidence": 0.95,
        "expected_en": "Nour",
        "expected_ar": "نور",
    }


def _valid_risk() -> dict:
    return {
        "category": "profanity",
        "language": "ar",
        "span": "بعض الكلمة",
        "severity": "block",
        "confidence": 0.92,
        "reason_en": "Contains profanity",
        "reason_ar": "يحتوي على ألفاظ نابية",
        "fix_en": "Remove the offensive word",
        "fix_ar": "أزل الكلمة المسيئة",
    }


def _valid_similar() -> dict:
    return {
        "registry_id": 42,
        "confusingly_similar": True,
        "reason_en": "Names are confusingly similar",
        "reason_ar": "الأسماء متشابهة بشكل مربك",
    }


def _valid_activity_fit() -> dict:
    return {
        "fits": True,
        "suggested_category_code": None,
        "reason_en": "Name is appropriate for the activity",
        "reason_ar": "الاسم مناسب للنشاط",
    }


def _valid_full_output() -> dict:
    return {
        "parse": _valid_parse(),
        "transliteration": _valid_transliteration(),
        "risks": [_valid_risk()],
        "similar": [_valid_similar()],
        "activity_fit": _valid_activity_fit(),
    }


# ---------------------------------------------------------------------------
# ParseOutput tests
# ---------------------------------------------------------------------------

class TestParseOutput:
    def test_valid(self):
        p = ParseOutput(**_valid_parse())
        assert p.core_ar == "نور"
        assert p.core_en == "Nour"
        assert p.activity_words == ["trading"]
        assert p.legal_form == "LLC"
        assert p.branch is False

    def test_defaults(self):
        p = ParseOutput(core_ar="a", core_en="b")
        assert p.activity_words == []
        assert p.legal_form is None
        assert p.branch is False

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            ParseOutput(core_ar="a")  # missing core_en


# ---------------------------------------------------------------------------
# TransliterationOutput tests
# ---------------------------------------------------------------------------

class TestTransliterationOutput:
    def test_valid(self):
        t = TransliterationOutput(**_valid_transliteration())
        assert t.consistent is True
        assert t.confidence == pytest.approx(0.95)

    def test_confidence_range(self):
        # Exactly 0.0 and 1.0 are valid
        TransliterationOutput(consistent=True, confidence=0.0, expected_en="a", expected_ar="b")
        TransliterationOutput(consistent=True, confidence=1.0, expected_en="a", expected_ar="b")

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            TransliterationOutput(consistent=True, confidence=1.1, expected_en="a", expected_ar="b")
        with pytest.raises(ValidationError):
            TransliterationOutput(consistent=True, confidence=-0.1, expected_en="a", expected_ar="b")


# ---------------------------------------------------------------------------
# RiskOutput tests
# ---------------------------------------------------------------------------

class TestRiskOutput:
    def test_valid(self):
        r = RiskOutput(**_valid_risk())
        assert r.category == "profanity"
        assert r.severity == "block"
        assert r.language == "ar"
        assert r.confidence == pytest.approx(0.92)

    def test_all_valid_categories(self):
        valid_cats = [
            "prohibited", "profanity", "unfriendly", "special",
            "divine_name", "location", "family_name",
            "impersonation", "misleading",
        ]
        base = _valid_risk()
        for cat in valid_cats:
            base["category"] = cat
            r = RiskOutput(**base)
            assert r.category == cat

    def test_invalid_category(self):
        bad = _valid_risk()
        bad["category"] = "unknown_category"
        with pytest.raises(ValidationError):
            RiskOutput(**bad)

    def test_all_valid_severities(self):
        base = _valid_risk()
        for sev in ("block", "review", "info"):
            base["severity"] = sev
            r = RiskOutput(**base)
            assert r.severity == sev

    def test_invalid_severity(self):
        bad = _valid_risk()
        bad["severity"] = "critical"
        with pytest.raises(ValidationError):
            RiskOutput(**bad)

    def test_all_valid_languages(self):
        base = _valid_risk()
        for lang in ("ar", "en", "both"):
            base["language"] = lang
            r = RiskOutput(**base)
            assert r.language == lang

    def test_invalid_language(self):
        bad = _valid_risk()
        bad["language"] = "fr"
        with pytest.raises(ValidationError):
            RiskOutput(**bad)

    def test_semantic_only_categories(self):
        """impersonation and misleading are LLM-only (not in lexicon)."""
        for cat in ("impersonation", "misleading"):
            d = _valid_risk()
            d["category"] = cat
            r = RiskOutput(**d)
            assert r.category == cat


# ---------------------------------------------------------------------------
# SimilarityJudgement tests
# ---------------------------------------------------------------------------

class TestSimilarityJudgement:
    def test_valid(self):
        s = SimilarityJudgement(**_valid_similar())
        assert s.registry_id == 42
        assert s.confusingly_similar is True

    def test_missing_registry_id(self):
        bad = _valid_similar()
        del bad["registry_id"]
        with pytest.raises(ValidationError):
            SimilarityJudgement(**bad)


# ---------------------------------------------------------------------------
# ActivityFitOutput tests
# ---------------------------------------------------------------------------

class TestActivityFitOutput:
    def test_valid_fits(self):
        a = ActivityFitOutput(**_valid_activity_fit())
        assert a.fits is True
        assert a.suggested_category_code is None

    def test_not_fits_with_suggestion(self):
        a = ActivityFitOutput(
            fits=False,
            suggested_category_code="TECH_001",
            reason_en="Name does not fit",
            reason_ar="الاسم لا يتناسب",
        )
        assert a.fits is False
        assert a.suggested_category_code == "TECH_001"


# ---------------------------------------------------------------------------
# LlmAnalyzerOutput (root model) tests
# ---------------------------------------------------------------------------

class TestLlmAnalyzerOutput:
    def test_full_valid_output(self):
        out = LlmAnalyzerOutput(**_valid_full_output())
        assert out.parse.core_ar == "نور"
        assert len(out.risks) == 1
        assert len(out.similar) == 1
        assert out.activity_fit.fits is True
        assert out.transliteration.consistent is True

    def test_empty_risks_and_similar(self):
        d = _valid_full_output()
        d["risks"] = []
        d["similar"] = []
        out = LlmAnalyzerOutput(**d)
        assert out.risks == []
        assert out.similar == []

    def test_missing_parse(self):
        d = _valid_full_output()
        del d["parse"]
        with pytest.raises(ValidationError):
            LlmAnalyzerOutput(**d)

    def test_missing_transliteration(self):
        d = _valid_full_output()
        del d["transliteration"]
        with pytest.raises(ValidationError):
            LlmAnalyzerOutput(**d)

    def test_missing_activity_fit(self):
        d = _valid_full_output()
        del d["activity_fit"]
        with pytest.raises(ValidationError):
            LlmAnalyzerOutput(**d)

    def test_json_roundtrip(self):
        out = LlmAnalyzerOutput(**_valid_full_output())
        json_str = out.model_dump_json()
        restored = LlmAnalyzerOutput.model_validate_json(json_str)
        assert restored.parse.core_ar == out.parse.core_ar
        assert len(restored.risks) == len(out.risks)

    def test_multiple_risks(self):
        d = _valid_full_output()
        risk2 = _valid_risk()
        risk2["category"] = "misleading"
        risk2["severity"] = "review"
        risk2["confidence"] = 0.7
        d["risks"] = [_valid_risk(), risk2]
        out = LlmAnalyzerOutput(**d)
        assert len(out.risks) == 2
        assert out.risks[1].category == "misleading"
