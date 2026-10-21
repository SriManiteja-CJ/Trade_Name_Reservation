"""
tests/test_decision_policy.py
Unit tests for Stage ⑤ Decision Policy (pipeline/decision_policy.py).

Spec references:
  §4.1 — Decision rules table
  N1   — Fail closed: AI outage never approves a name
  N4   — Every flag explained in AR + EN
  N9   — Existing legacy boolean fields preserved
  F14  — Accept-Language / lang header determines primary message language
"""
import pytest
from config.settings import FlagMode, get_settings
from pipeline.decision_policy import Outcome, apply_policy
from pipeline.deterministic_gates import GateSignal, SignalType


def test_decision_policy_clean_name_ai_off():
    """When AI is off and gates produce no signals, outcome is OK."""
    settings = get_settings()
    settings.ai_analyzer = FlagMode.off

    result = apply_policy(gate_signals=[], llm_output=None)
    assert result.outcome == Outcome.OK
    assert len(result.reasons) == 0
    assert result.legacy_flags["Prohibted"] is False
    assert result.legacy_flags["Similarity"] is False


def test_decision_policy_hard_block_gate():
    """Hard gate hit always produces BLOCKED."""
    signal = GateSignal(
        signal_type=SignalType.BLOCKED,
        source="exact_duplicate",
        reason_en="Duplicate name",
        reason_ar="اسم مكرر",
        fix_en="Choose another",
        fix_ar="اختر اسماً آخر",
    )
    result = apply_policy(gate_signals=[signal], llm_output=None)
    assert result.outcome == Outcome.BLOCKED
    assert len(result.reasons) == 1
    assert result.reasons[0].reason_en == "Duplicate name"
    assert result.reasons[0].reason_ar == "اسم مكرر"


def test_decision_policy_review_gate():
    """Review gate signal produces NEEDS_REVIEW."""
    signal = GateSignal(
        signal_type=SignalType.NEEDS_REVIEW,
        source="lexicon",
        category="location",
        severity="review",
        reason_en="Location name used",
        reason_ar="تم استخدام اسم موقع",
        fix_en="Remove location",
        fix_ar="أزل الموقع",
    )
    result = apply_policy(gate_signals=[signal], llm_output=None)
    assert result.outcome == Outcome.NEEDS_REVIEW
    assert result.legacy_flags["LocationNames"] is True


def test_decision_policy_n1_fail_closed_during_ai_outage():
    """N1: When AI is ON but LLM is unavailable (None), outcome must be NEEDS_REVIEW, never OK."""
    settings = get_settings()
    settings.ai_analyzer = FlagMode.on

    try:
        result = apply_policy(gate_signals=[], llm_output=None)
        assert result.outcome == Outcome.NEEDS_REVIEW
    finally:
        settings.ai_analyzer = FlagMode.off


def test_decision_policy_legacy_flags_mapping():
    """Verify legacy boolean flags (including typo Prohibted) are populated correctly."""
    signal = GateSignal(
        signal_type=SignalType.BLOCKED,
        source="lexicon",
        category="prohibited",
        severity="block",
    )
    result = apply_policy(gate_signals=[signal], llm_output=None)
    assert result.outcome == Outcome.BLOCKED
    assert result.legacy_flags["Prohibted"] is True
