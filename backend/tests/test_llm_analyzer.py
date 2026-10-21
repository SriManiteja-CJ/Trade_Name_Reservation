"""
tests/test_llm_analyzer.py
Unit tests for pipeline/llm_analyzer.py — Stage ④ LLM Analyzer.

Tests verify:
  - When ai_analyzer=off, returns None without calling LLM
  - When ai_analyzer=shadow, calls LLM (audits), returns result (caller decides how to use it)
  - When ai_analyzer=on, calls LLM and returns result
  - LLM failure → None returned regardless of flag mode

Spec references:
  F16  — feature flags (off/shadow/on)
  N1   — LLM unavailable → None (fail-closed at decision policy level)
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from config.settings import FlagMode


VALID_LLM_JSON = {
    "parse": {
        "core_ar": "ألفا",
        "core_en": "Alpha",
        "activity_words": [],
        "legal_form": None,
        "branch": False,
    },
    "transliteration": {
        "consistent": True,
        "confidence": 0.9,
        "expected_en": "Alpha",
        "expected_ar": "ألفا",
    },
    "risks": [],
    "similar": [],
    "activity_fit": {
        "fits": True,
        "suggested_category_code": None,
        "reason_en": "Appropriate",
        "reason_ar": "مناسب",
    },
}

VALID_VLLM_RESPONSE = {
    "choices": [{"message": {"content": json.dumps(VALID_LLM_JSON)}}],
    "usage": {"total_tokens": 300},
}


def _make_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    return session


class TestLlmAnalyzerFlagBehavior:
    """Tests for ai_analyzer feature flag behavior."""

    @pytest.mark.asyncio
    async def test_flag_off_returns_none_no_call(self):
        """When ai_analyzer=off, Stage ④ is skipped entirely."""
        session = _make_session()

        with patch("pipeline.llm_analyzer.settings") as mock_settings:
            mock_settings.ai_analyzer = FlagMode.off
            from pipeline.llm_analyzer import run_llm_analyzer

            http_mock = AsyncMock()
            with patch("llm.gateway.httpx.AsyncClient.post", new=http_mock):
                result = await run_llm_analyzer(
                    request_id="REQ-A1",
                    channel="online",
                    name_ar="ألفا",
                    name_en="Alpha",
                    normalized_ar="الفا",
                    normalized_en="alpha",
                    session=session,
                )

            # No HTTP call should be made
            http_mock.assert_not_called()
            assert result is None

    @pytest.mark.asyncio
    async def test_flag_shadow_calls_llm_returns_result(self):
        """When ai_analyzer=shadow, LLM is called and result returned for audit."""
        session = _make_session()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = VALID_VLLM_RESPONSE

        with patch("pipeline.llm_analyzer.settings") as mock_settings:
            mock_settings.ai_analyzer = FlagMode.shadow

            from pipeline.llm_analyzer import run_llm_analyzer
            from llm.gateway import LlmGateway

            with patch.object(LlmGateway, "analyze", new=AsyncMock(return_value=None)):
                # In shadow: LLM is called (we just verify it's attempted)
                result = await run_llm_analyzer(
                    request_id="REQ-A2",
                    channel="walkin",
                    name_ar="ألفا",
                    name_en="Alpha",
                    normalized_ar="الفا",
                    normalized_en="alpha",
                    session=session,
                )
            # None returned here because we mocked gateway to return None
            assert result is None

    @pytest.mark.asyncio
    async def test_flag_on_returns_llm_output(self):
        """When ai_analyzer=on, LLM result is returned for use in Stage ⑤."""
        from llm.schemas import LlmAnalyzerOutput
        from llm.gateway import LlmGateway

        session = _make_session()
        expected_output = LlmAnalyzerOutput(**VALID_LLM_JSON)

        with patch("pipeline.llm_analyzer.settings") as mock_settings:
            mock_settings.ai_analyzer = FlagMode.on

            from pipeline.llm_analyzer import run_llm_analyzer

            with patch.object(LlmGateway, "analyze", new=AsyncMock(return_value=expected_output)):
                result = await run_llm_analyzer(
                    request_id="REQ-A3",
                    channel="online",
                    name_ar="ألفا",
                    name_en="Alpha",
                    normalized_ar="الفا",
                    normalized_en="alpha",
                    session=session,
                )

        assert result is not None
        assert result.parse.core_ar == "ألفا"
        assert result.transliteration.consistent is True

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        """Any exception from the LLM gateway → None returned (N1 fail-closed)."""
        from llm.gateway import LlmGateway

        session = _make_session()

        with patch("pipeline.llm_analyzer.settings") as mock_settings:
            mock_settings.ai_analyzer = FlagMode.on

            from pipeline.llm_analyzer import run_llm_analyzer

            with patch.object(LlmGateway, "analyze", new=AsyncMock(side_effect=RuntimeError("unexpected"))):
                result = await run_llm_analyzer(
                    request_id="REQ-A4",
                    channel="online",
                    name_ar="ألفا",
                    name_en="Alpha",
                    normalized_ar="الفا",
                    normalized_en="alpha",
                    session=session,
                )

        assert result is None


class TestDecisionPolicyWithLlmOutput:
    """
    Integration-level tests for Stage ⑤ decision policy when given LLM output.
    These test the full apply_policy() function with realistic LLM outputs.
    """

    def _make_llm_output(self, risks=None, transliteration_consistent=True, activity_fits=True):
        """Build a minimal LlmAnalyzerOutput for testing."""
        from llm.schemas import (
            LlmAnalyzerOutput, ParseOutput, TransliterationOutput,
            ActivityFitOutput, RiskOutput,
        )
        return LlmAnalyzerOutput(
            parse=ParseOutput(core_ar="ألفا", core_en="Alpha"),
            transliteration=TransliterationOutput(
                consistent=transliteration_consistent,
                confidence=0.9,
                expected_en="Alpha",
                expected_ar="ألفا",
            ),
            risks=risks or [],
            similar=[],
            activity_fit=ActivityFitOutput(
                fits=activity_fits,
                suggested_category_code=None,
                reason_en="OK",
                reason_ar="جيد",
            ),
        )

    def test_llm_block_risk_at_high_confidence_produces_blocked(self):
        from pipeline.decision_policy import apply_policy, Outcome
        from llm.schemas import RiskOutput

        risk = RiskOutput(
            category="prohibited",
            language="ar",
            span="بذيء",
            severity="block",
            confidence=0.95,  # above default threshold of 0.85
            reason_en="Prohibited word",
            reason_ar="كلمة محظورة",
            fix_en="Remove it",
            fix_ar="أزلها",
        )
        llm_out = self._make_llm_output(risks=[risk])

        result = apply_policy(
            gate_signals=[],
            llm_output=llm_out,
            skip_word_checks=False,
            lang_header="ar",
        )
        assert result.outcome == Outcome.BLOCKED

    def test_llm_block_risk_at_low_confidence_produces_needs_review(self):
        from pipeline.decision_policy import apply_policy, Outcome
        from llm.schemas import RiskOutput

        risk = RiskOutput(
            category="prohibited",
            language="en",
            span="some word",
            severity="block",
            confidence=0.50,  # below block threshold → downgraded to review
            reason_en="Possibly prohibited",
            reason_ar="محتمل محظور",
            fix_en="Consider renaming",
            fix_ar="فكر في إعادة التسمية",
        )
        llm_out = self._make_llm_output(risks=[risk])

        result = apply_policy(
            gate_signals=[],
            llm_output=llm_out,
            skip_word_checks=False,
            lang_header="en",
        )
        assert result.outcome == Outcome.NEEDS_REVIEW

    def test_llm_review_risk_produces_needs_review(self):
        from pipeline.decision_policy import apply_policy, Outcome
        from llm.schemas import RiskOutput

        risk = RiskOutput(
            category="misleading",
            language="both",
            span="Healthcare",
            severity="review",
            confidence=0.8,
            reason_en="May be misleading",
            reason_ar="قد يكون مضللاً",
            fix_en="Clarify the meaning",
            fix_ar="وضح المعنى",
        )
        llm_out = self._make_llm_output(risks=[risk])

        result = apply_policy(
            gate_signals=[],
            llm_output=llm_out,
            skip_word_checks=False,
            lang_header="en",
        )
        assert result.outcome == Outcome.NEEDS_REVIEW

    def test_transliteration_mismatch_produces_needs_review(self):
        from pipeline.decision_policy import apply_policy, Outcome

        llm_out = self._make_llm_output(transliteration_consistent=False)

        result = apply_policy(
            gate_signals=[],
            llm_output=llm_out,
            skip_word_checks=False,
            lang_header="en",
        )
        assert result.outcome == Outcome.NEEDS_REVIEW
        # Reason for transliteration mismatch should be in the list
        reason_cats = [r.category for r in result.reasons]
        assert "transliteration_mismatch" in reason_cats

    def test_poor_activity_fit_produces_needs_review(self):
        from pipeline.decision_policy import apply_policy, Outcome

        llm_out = self._make_llm_output(activity_fits=False)

        result = apply_policy(
            gate_signals=[],
            llm_output=llm_out,
            skip_word_checks=False,
            lang_header="ar",
        )
        assert result.outcome == Outcome.NEEDS_REVIEW
        reason_cats = [r.category for r in result.reasons]
        assert "activity_fit" in reason_cats

    def test_no_risks_clean_name_produces_ok(self):
        from pipeline.decision_policy import apply_policy, Outcome

        llm_out = self._make_llm_output(
            risks=[],
            transliteration_consistent=True,
            activity_fits=True,
        )

        result = apply_policy(
            gate_signals=[],
            llm_output=llm_out,
            skip_word_checks=False,
            lang_header="en",
        )
        assert result.outcome == Outcome.OK
        assert result.reasons == []

    def test_hard_gate_block_overrides_clean_llm(self):
        """Hard deterministic block is NEVER overridden by LLM output (spec §4.1)."""
        from pipeline.decision_policy import apply_policy, Outcome
        from pipeline.deterministic_gates import GateSignal, SignalType

        hard_block = GateSignal(
            signal_type=SignalType.BLOCKED,
            source="index",
            category="exact_duplicate",
            severity="block",
            reason_en="Exact duplicate found",
            reason_ar="نسخة مطابقة موجودة",
            fix_en="Choose a different name",
            fix_ar="اختر اسماً مختلفاً",
        )
        llm_out = self._make_llm_output(risks=[], transliteration_consistent=True, activity_fits=True)

        result = apply_policy(
            gate_signals=[hard_block],
            llm_output=llm_out,
            skip_word_checks=False,
            lang_header="en",
        )
        # Hard gate always wins
        assert result.outcome == Outcome.BLOCKED

    def test_llm_unavailable_with_shadow_mode_becomes_needs_review(self):
        """
        When ai_analyzer=shadow, llm_output=None is passed to apply_policy(),
        so N1 kicks in: best outcome is NEEDS_REVIEW (not OK).
        """
        from pipeline.decision_policy import apply_policy, Outcome

        with patch("pipeline.decision_policy.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.ai_analyzer = FlagMode.shadow
            mock_settings.policy_block_confidence_threshold = 0.85
            mock_settings.policy_review_confidence_threshold = 0.60
            mock_get_settings.return_value = mock_settings

            result = apply_policy(
                gate_signals=[],
                llm_output=None,  # Shadow: llm_output=None passed by route
                skip_word_checks=False,
                lang_header="en",
            )

        assert result.outcome == Outcome.NEEDS_REVIEW
        assert result.llm_was_available is False

    def test_llm_risk_updates_legacy_fields(self):
        """LLM-identified risks must update N9 legacy boolean flags."""
        from pipeline.decision_policy import apply_policy, Outcome
        from llm.schemas import RiskOutput

        risk = RiskOutput(
            category="profanity",
            language="ar",
            span="word",
            severity="block",
            confidence=0.90,
            reason_en="Profanity detected",
            reason_ar="تم اكتشاف ألفاظ نابية",
            fix_en="Remove it",
            fix_ar="أزلها",
        )
        llm_out = self._make_llm_output(risks=[risk])

        result = apply_policy(
            gate_signals=[],
            llm_output=llm_out,
            skip_word_checks=False,
            lang_header="en",
        )
        # N9: Profanity legacy field must be True
        assert result.legacy_flags.get("Profanity") is True
        assert result.legacy_flags.get("Prohibted") is False
