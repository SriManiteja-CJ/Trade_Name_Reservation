"""
tests/test_llm_gateway.py
Unit tests for the LLM Gateway (Phase 2.1) — circuit breaker, caching, retry,
audit write, and shadow-mode wiring.

These tests mock httpx and Redis/DB to keep things fast and isolated.
Spec references validated:
  §6.2   — timeout, retry, circuit breaker, 24h cache
  N1     — LLM unavailable → circuit OPEN, returns None
  N3     — Audit row written on every call (success or failure)
  §4.3   — Schema validation failure → None returned
  F16    — Feature flag shadow/on/off controls Stage ④
"""
import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
import httpx

from llm.gateway import CircuitBreaker, CircuitState, LlmGateway, _make_cache_key
from llm.schemas import LlmAnalyzerOutput

@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    from llm import gateway as gw_module
    gw_module._circuit_breaker.record_success()
    yield


# ---------------------------------------------------------------------------
# Helpers — valid LLM output fixture
# ---------------------------------------------------------------------------

VALID_LLM_JSON = {
    "parse": {
        "core_ar": "نور",
        "core_en": "Nour",
        "activity_words": ["trading"],
        "legal_form": None,
        "branch": False,
    },
    "transliteration": {
        "consistent": True,
        "confidence": 0.95,
        "expected_en": "Nour",
        "expected_ar": "نور",
    },
    "risks": [],
    "similar": [],
    "activity_fit": {
        "fits": True,
        "suggested_category_code": None,
        "reason_en": "Name is appropriate",
        "reason_ar": "الاسم مناسب",
    },
}

VALID_VLLM_RESPONSE = {
    "choices": [
        {
            "message": {
                "content": json.dumps(VALID_LLM_JSON),
                "role": "assistant",
            }
        }
    ],
    "usage": {"total_tokens": 512},
}


def _mock_session():
    """Create a mock async DB session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    
    @asynccontextmanager
    async def mock_begin_nested():
        yield MagicMock()
        
    session.begin_nested = mock_begin_nested
    return session


def _mock_audit_session_factory():
    """Create an isolated session factory for audit writes."""
    audit_session = AsyncMock()
    audit_session.add = MagicMock()
    audit_session.flush = AsyncMock()
    audit_session.commit = AsyncMock()

    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=audit_session)
    context.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=context)
    return factory, audit_session


# ---------------------------------------------------------------------------
# Circuit Breaker unit tests
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=30)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available() is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=30)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available() is False

    def test_does_not_open_before_threshold(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=30)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available() is True

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(threshold=3, cooldown_seconds=30)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.consecutive_failures == 0
        assert cb.state == CircuitState.CLOSED

    def test_half_open_after_cooldown(self):
        cb = CircuitBreaker(threshold=2, cooldown_seconds=0)  # instant cooldown
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # With cooldown=0, the next is_available() call should move to HALF_OPEN
        assert cb.is_available() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_closed_after_success_in_half_open(self):
        cb = CircuitBreaker(threshold=2, cooldown_seconds=0)
        cb.record_failure()
        cb.record_failure()
        cb.is_available()  # transitions to HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# Cache key uniqueness tests
# ---------------------------------------------------------------------------

class TestCacheKey:
    def test_different_names_produce_different_keys(self):
        k1 = _make_cache_key("نور", "Nour", None, None, "v1")
        k2 = _make_cache_key("نجم", "Najm", None, None, "v1")
        assert k1 != k2

    def test_different_prompt_versions_produce_different_keys(self):
        k1 = _make_cache_key("نور", "Nour", None, None, "v1")
        k2 = _make_cache_key("نور", "Nour", None, None, "v2")
        assert k1 != k2

    def test_same_inputs_produce_same_key(self):
        k1 = _make_cache_key("نور", "Nour", "tech", "LLC", "v1")
        k2 = _make_cache_key("نور", "Nour", "tech", "LLC", "v1")
        assert k1 == k2

    def test_key_prefixed_correctly(self):
        k = _make_cache_key("a", "b", None, None, "v1")
        assert k.startswith("tnis:llm:")


# ---------------------------------------------------------------------------
# LlmGateway.analyze() — success path
# ---------------------------------------------------------------------------

class TestGatewaySuccessPath:
    @pytest.mark.asyncio
    async def test_successful_call_returns_output(self):
        session = _mock_session()
        gateway = LlmGateway(session=session, redis_client=None)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = VALID_VLLM_RESPONSE

        with patch.object(gateway._http_client, "post", new=AsyncMock(return_value=mock_response)):
            result = await gateway.analyze(
                request_id="REQ-001",
                channel="online",
                name_ar="نور",
                name_en="Nour",
                normalized_ar="نور",
                normalized_en="nour",
                system_prompt="You are a compliance specialist.",
                prompt_version_label="analyzer_v1_v1",
            )

        assert result is not None
        assert isinstance(result, LlmAnalyzerOutput)
        assert result.parse.core_ar == "نور"
        assert result.transliteration.consistent is True

    @pytest.mark.asyncio
    async def test_audit_written_on_success(self):
        session = _mock_session()
        gateway = LlmGateway(session=session, redis_client=None)
        audit_factory, audit_session = _mock_audit_session_factory()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = VALID_VLLM_RESPONSE

        with patch("db.session.AsyncSessionLocal", audit_factory), patch.object(
            gateway._http_client, "post", new=AsyncMock(return_value=mock_response)
        ):
            await gateway.analyze(
                request_id="REQ-002",
                channel="online",
                name_ar="نور",
                name_en="Nour",
                normalized_ar="نور",
                normalized_en="nour",
                system_prompt="prompt",
                prompt_version_label="v1",
            )

        audit_factory.assert_called_once()
        audit_session.add.assert_called_once()
        audit_session.flush.assert_awaited_once()
        audit_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# LlmGateway.analyze() — failure paths
# ---------------------------------------------------------------------------

class TestGatewayFailurePaths:
    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        session = _mock_session()
        gateway = LlmGateway(session=session, redis_client=None)

        with patch.object(
            gateway._http_client, "post",
            new=AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        ):
            result = await gateway.analyze(
                request_id="REQ-003",
                channel="online",
                name_ar="نور",
                name_en="Nour",
                normalized_ar="نور",
                normalized_en="nour",
                system_prompt="prompt",
                prompt_version_label="v1",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_schema_failure_returns_none(self):
        """Invalid JSON from LLM → schema error → None (spec §4.3)."""
        session = _mock_session()
        gateway = LlmGateway(session=session, redis_client=None)

        bad_response = MagicMock()
        bad_response.status_code = 200
        bad_response.json.return_value = {
            "choices": [{"message": {"content": '{"invalid": "schema"}'}}],
            "usage": {"total_tokens": 10},
        }

        with patch.object(gateway._http_client, "post", new=AsyncMock(return_value=bad_response)):
            result = await gateway.analyze(
                request_id="REQ-004",
                channel="online",
                name_ar="نور",
                name_en="Nour",
                normalized_ar="نور",
                normalized_en="nour",
                system_prompt="prompt",
                prompt_version_label="v1",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_audit_written_on_failure(self):
        """Audit must be written even when LLM fails (N3)."""
        session = _mock_session()
        gateway = LlmGateway(session=session, redis_client=None)
        audit_factory, audit_session = _mock_audit_session_factory()

        with patch("db.session.AsyncSessionLocal", audit_factory), patch.object(
            gateway._http_client, "post",
            new=AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        ):
            await gateway.analyze(
                request_id="REQ-005",
                channel="online",
                name_ar="نور",
                name_en="Nour",
                normalized_ar="نور",
                normalized_en="nour",
                system_prompt="prompt",
                prompt_version_label="v1",
            )

        audit_factory.assert_called_once()
        audit_session.add.assert_called_once()
        audit_session.flush.assert_awaited_once()
        audit_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_circuit_open_returns_none_immediately(self):
        """When circuit is OPEN, no HTTP call is made and None is returned (N1)."""
        session = _mock_session()
        gateway = LlmGateway(session=session, redis_client=None)

        # Force circuit open
        from llm import gateway as gw_module
        original_cb = gw_module._circuit_breaker
        try:
            from llm.gateway import CircuitBreaker
            gw_module._circuit_breaker = CircuitBreaker(threshold=1, cooldown_seconds=9999)
            gw_module._circuit_breaker.record_failure()  # opens immediately
            assert gw_module._circuit_breaker.state == CircuitState.OPEN

            http_mock = AsyncMock()
            with patch.object(gateway._http_client, "post", new=http_mock):
                result = await gateway.analyze(
                    request_id="REQ-006",
                    channel="online",
                    name_ar="نور",
                    name_en="Nour",
                    normalized_ar="نور",
                    normalized_en="nour",
                    system_prompt="prompt",
                    prompt_version_label="v1",
                )

            # HTTP must NOT have been called
            http_mock.assert_not_called()
            assert result is None
        finally:
            gw_module._circuit_breaker = original_cb

    @pytest.mark.asyncio
    async def test_5xx_triggers_retry_then_fails(self):
        """Server 5xx → one retry → None returned."""
        session = _mock_session()
        gateway = LlmGateway(session=session, redis_client=None)

        bad_response = MagicMock()
        bad_response.status_code = 503
        bad_response.json.return_value = {}

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return bad_response

        with patch.object(gateway._http_client, "post", new=mock_post):
            result = await gateway.analyze(
                request_id="REQ-007",
                channel="walkin",
                name_ar="نور",
                name_en="Nour",
                normalized_ar="نور",
                normalized_en="nour",
                system_prompt="prompt",
                prompt_version_label="v1",
            )

        # Should attempt 1 + 1 retry = 2 calls
        assert call_count == 2
        assert result is None


# ---------------------------------------------------------------------------
# Shadow-mode wiring tests
# ---------------------------------------------------------------------------

class TestShadowModeWiring:
    def test_is_shadow_mode_when_flag_shadow(self):
        """is_shadow_mode() returns True when ai_analyzer=shadow."""
        with patch("pipeline.decision_policy.settings") as mock_settings:
            from config.settings import FlagMode
            mock_settings.ai_analyzer = FlagMode.shadow
            from pipeline.decision_policy import is_shadow_mode
            assert is_shadow_mode() is True

    def test_is_not_shadow_mode_when_flag_on(self):
        with patch("pipeline.decision_policy.settings") as mock_settings:
            from config.settings import FlagMode
            mock_settings.ai_analyzer = FlagMode.on
            from pipeline.decision_policy import is_shadow_mode
            assert is_shadow_mode() is False

    def test_is_not_shadow_mode_when_flag_off(self):
        with patch("pipeline.decision_policy.settings") as mock_settings:
            from config.settings import FlagMode
            mock_settings.ai_analyzer = FlagMode.off
            from pipeline.decision_policy import is_shadow_mode
            assert is_shadow_mode() is False
