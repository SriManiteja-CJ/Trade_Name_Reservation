"""
llm/gateway.py
LLM Gateway — the single integration point between the TNIS pipeline and the
self-hosted vLLM instance (spec §3.1, §6.2, Phase 2.1).

Responsibilities:
  - Calls the vLLM OpenAI-compatible endpoint for analysis
  - Enforces 2.5 s timeout (configurable) on the validation path
  - One retry on transient errors (5xx / network timeout)
  - Circuit breaker: opens after N consecutive failures; half-opens after cooldown
  - Response cache: Redis, keyed by SHA-256 of (normalized_ar + normalized_en +
    activity_category + legal_form + prompt_version), TTL = 24 h
  - Schema validation: parses raw JSON into LlmAnalyzerOutput; failure = unavailable
  - Audit write: AiDecisionAudit row after every call (success or failure)
  - Prompt injection resistance: name inserted inside XML tags (N6)

Spec references:
  §6.2   — LLM gateway spec (timeout, retry, circuit breaker, cache)
  N1     — LLM unavailable → fail closed (never auto-approve)
  N3     — Every AI call audited with request_id, prompt_version, model_id
  N5     — All calls go to internal DED vLLM; no external LLM calls
  N6     — Input hash; no raw PII stored in audit; XML tag injection resistance
  §4.3   — Schema failure treated as LLM unavailable
"""
import asyncio
import hashlib
import json
import logging
import time
from enum import Enum
from typing import Optional, Any

import httpx
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from audit.repository import AuditRepository, compute_input_hash
from config.settings import get_settings
from llm.schemas import (
    CategorySuggestionOutput,
    LexiconVariantsOutput,
    LlmAnalyzerOutput,
    ReviewerBriefOutput,
    SuggestionBatchOutput,
    TransliterationCheckOutput,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Circuit Breaker State Machine
# ---------------------------------------------------------------------------

class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing fast
    HALF_OPEN = "half_open" # Testing recovery


class CircuitBreaker:
    """
    Simple in-process circuit breaker (spec §6.2).

    Opens after `threshold` consecutive failures.
    Moves to HALF_OPEN after `cooldown_seconds` in OPEN state.
    Closes again after one successful call in HALF_OPEN.
    """

    def __init__(self, threshold: int, cooldown_seconds: int) -> None:
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.state = CircuitState.CLOSED
        self.consecutive_failures: int = 0
        self.opened_at: Optional[float] = None

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.state = CircuitState.CLOSED
        self.opened_at = None

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.threshold:
            if self.state != CircuitState.OPEN:
                self.state = CircuitState.OPEN
                self.opened_at = time.monotonic()
                logger.warning(
                    "circuit_breaker_opened",
                    extra={"consecutive_failures": self.consecutive_failures}
                )

    def is_available(self) -> bool:
        """Return True if a call should be attempted."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if (
                self.opened_at is not None
                and (time.monotonic() - self.opened_at) >= self.cooldown_seconds
            ):
                self.state = CircuitState.HALF_OPEN
                logger.info("circuit_breaker_half_open")
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return True
        return False


# ---------------------------------------------------------------------------
# Module-level circuit breaker (singleton per process)
# ---------------------------------------------------------------------------
_circuit_breaker = CircuitBreaker(
    threshold=settings.llm_circuit_breaker_threshold,
    cooldown_seconds=settings.llm_circuit_breaker_cooldown,
)


# ---------------------------------------------------------------------------
# Cache key computation
# ---------------------------------------------------------------------------

def _make_cache_key(
    normalized_ar: str,
    normalized_en: str,
    activity_category: Optional[str],
    legal_form: Optional[str],
    prompt_version: str,
) -> str:
    """
    SHA-256 cache key for the LLM response cache (spec §6.2).
    Includes prompt_version so a prompt update busts the cache.
    """
    raw = (
        f"{normalized_ar}||{normalized_en}||"
        f"{activity_category or ''}||{legal_form or ''}||"
        f"{prompt_version}"
    )
    return "tnis:llm:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _format_response_format(schema: Optional[dict] = None) -> dict[str, Any]:
    """
    Format response_format appropriately for different LLM backends.
    vLLM guided decoding accepts {"type": "json_object", "schema": ...}.
    OpenAI, Groq, and Ollama standard APIs accept {"type": "json_object"}.
    """
    cfg = get_settings()
    provider = (cfg.llm_provider or "").lower().strip()
    if provider == "vllm" and schema:
        return {"type": "json_object", "schema": schema}
    return {"type": "json_object"}


# ---------------------------------------------------------------------------
# LLM Gateway
# ---------------------------------------------------------------------------

class LlmGateway:
    """
    The single LLM integration point for the Trade Name Intelligence Service.

    Usage:
        gateway = LlmGateway(redis_client=..., session=...)
        result = await gateway.analyze(
            name_ar="...", name_en="...", ...
        )
        # result is LlmAnalyzerOutput | None (None = LLM unavailable)
    """

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Optional[Any] = None,   # aioredis client; None disables caching
    ) -> None:
        self.session = session
        self.redis = redis_client
        cfg = get_settings()
        headers = {}
        api_key = cfg.effective_api_key
        if api_key and api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        self._http_client = httpx.AsyncClient(
            base_url=cfg.effective_llm_base_url,
            headers=headers,
            timeout=httpx.Timeout(cfg.llm_timeout_seconds),
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http_client.aclose()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http_client.aclose()

    async def analyze(
        self,
        *,
        request_id: str,
        channel: str,
        name_ar: str,
        name_en: str,
        activity_category: Optional[str] = None,
        legal_form: Optional[str] = None,
        similar_names: Optional[list[dict]] = None,
        system_prompt: str,
        prompt_version_label: str,
        # composed normalized forms for cache key / audit hash
        normalized_ar: str,
        normalized_en: str,
    ) -> Optional[LlmAnalyzerOutput]:
        """
        Run the LLM Analyzer (Stage ④). Returns LlmAnalyzerOutput or None.

        Steps:
          1. Check circuit breaker → if OPEN, return None immediately
          2. Check Redis cache → if hit, return cached result
          3. Call vLLM with timeout + one retry
          4. Parse into LlmAnalyzerOutput; schema failure → None
          5. Write AiDecisionAudit row
          6. Update circuit breaker state
          7. Cache successful result in Redis

        Args:
            request_id:          DED application request ID (N3)
            channel:             "online" | "walkin"
            name_ar:             Arabic trade name (raw, for user message)
            name_en:             English trade name (raw, for user message)
            activity_category:   Declared activity category
            legal_form:          Legal form token
            similar_names:       Top similar names from Stage ③ (list of dicts)
            system_prompt:       Loaded system prompt text
            prompt_version_label: Version label for audit (e.g. "analyzer_v1_v42")
            normalized_ar:       Normalized Arabic form (for cache key / input hash)
            normalized_en:       Normalized English form (for cache key / input hash)

        Returns:
            LlmAnalyzerOutput if successful, None if unavailable or schema failure.
        """
        # Build input hash for audit (N6 — no raw PII)
        input_hash = compute_input_hash(
            normalized_ar=normalized_ar,
            normalized_en=normalized_en,
            legal_form=legal_form,
        )

        cache_key = _make_cache_key(
            normalized_ar=normalized_ar,
            normalized_en=normalized_en,
            activity_category=activity_category,
            legal_form=legal_form,
            prompt_version=prompt_version_label,
        )

        # -----------------------------------------------------------------
        # Step 1: Circuit breaker check
        # -----------------------------------------------------------------
        if not _circuit_breaker.is_available():
            logger.warning(
                "llm_circuit_open_skip",
                extra={"request_id": request_id}
            )
            await self._write_audit(
                request_id=request_id,
                channel=channel,
                input_hash=input_hash,
                prompt_version=prompt_version_label,
                outcome="circuit_open",
                raw_output=None,
                latency_ms=None,
                tokens=None,
            )
            return None

        # -----------------------------------------------------------------
        # Step 2: Cache lookup
        # -----------------------------------------------------------------
        if self.redis:
            try:
                cached_raw = await self.redis.get(cache_key)
                if cached_raw:
                    logger.debug("llm_cache_hit", extra={"request_id": request_id})
                    parsed = LlmAnalyzerOutput.model_validate_json(cached_raw)
                    # Record audit with cache=True outcome
                    await self._write_audit(
                        request_id=request_id,
                        channel=channel,
                        input_hash=input_hash,
                        prompt_version=prompt_version_label,
                        outcome="cache_hit",
                        raw_output=parsed.model_dump(),
                        latency_ms=0,
                        tokens=None,
                    )
                    return parsed
            except Exception as cache_exc:
                logger.debug("llm_cache_error", extra={"error": str(cache_exc)})

        # -----------------------------------------------------------------
        # Step 3: Build request payload and call vLLM
        # -----------------------------------------------------------------
        from llm.prompts import build_analyzer_user_message

        user_message = build_analyzer_user_message(
            name_ar=name_ar,
            name_en=name_en,
            activity_category=activity_category,
            legal_form=legal_form,
            channel=channel,
            similar_names=similar_names,
        )

        cfg = get_settings()
        response_schema = LlmAnalyzerOutput.model_json_schema()
        payload = {
            "model": cfg.effective_analyzer_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0,       # Deterministic output per spec
            "max_tokens": 750,
            "response_format": _format_response_format(response_schema),
        }

        llm_output: Optional[LlmAnalyzerOutput] = None
        latency_ms: Optional[int] = None
        tokens: Optional[int] = None
        raw_dict: Optional[dict] = None
        outcome_label = "error"

        # One retry on transient errors (5xx / timeout) — spec §6.2
        for attempt in range(settings.llm_max_retries + 1):
            start_time = time.monotonic()
            try:
                response = await self._http_client.post(
                    "/chat/completions",
                    json=payload,
                )
                latency_ms = int((time.monotonic() - start_time) * 1000)

                if response.status_code >= 500:
                    logger.warning(
                        "llm_server_error",
                        extra={
                            "request_id": request_id,
                            "attempt": attempt,
                            "status_code": response.status_code,
                        }
                    )
                    if attempt < settings.llm_max_retries:
                        await asyncio.sleep(0.1 * (attempt + 1))  # brief backoff
                        continue
                    break

                if response.status_code != 200:
                    print("LLM RESPONSE ERROR:", response.status_code, response.text)
                    outcome_label = f"http_{response.status_code}"
                    _circuit_breaker.record_failure()
                    break

                # Parse LLM response envelope
                resp_json = response.json()
                raw_content: str = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                tokens = resp_json.get("usage", {}).get("total_tokens")

                # Step 4: Schema validation (§4.3 — failure = unavailable)
                try:
                    raw_dict = json.loads(raw_content)
                    llm_output = LlmAnalyzerOutput.model_validate(raw_dict)
                    outcome_label = "ok"
                    _circuit_breaker.record_success()
                    break  # Success
                except (json.JSONDecodeError, ValidationError, KeyError) as schema_err:
                    print("SCHEMA ERROR DETAIL:", repr(schema_err))
                    # Schema failure → treat as LLM unavailable (do NOT retry)
                    logger.error(
                        "llm_schema_validation_failed",
                        extra={
                            "request_id": request_id,
                            "error": str(schema_err),
                            "raw_content": raw_content[:500],
                        }
                    )
                    outcome_label = "schema_error"
                    _circuit_breaker.record_failure()
                    break  # No retry for schema errors

            except httpx.TimeoutException:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                logger.warning(
                    "llm_timeout",
                    extra={
                        "request_id": request_id,
                        "attempt": attempt,
                        "timeout_s": settings.llm_timeout_seconds,
                    }
                )
                if attempt < settings.llm_max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                outcome_label = "timeout"
                _circuit_breaker.record_failure()
                break

            except (httpx.RequestError, httpx.ConnectError) as conn_err:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                logger.error(
                    "llm_connection_error",
                    extra={"request_id": request_id, "error": str(conn_err)}
                )
                if attempt < settings.llm_max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                outcome_label = "connection_error"
                _circuit_breaker.record_failure()
                break

        # -----------------------------------------------------------------
        # Step 5: Write AiDecisionAudit row (N3)
        # -----------------------------------------------------------------
        # Outcome in audit = pipeline outcome (OK|NEEDS_REVIEW|BLOCKED) only known
        # later, so we store the LLM call status here; the route handler writes the
        # final pipeline outcome. This audit row captures the raw LLM interaction.
        await self._write_audit(
            request_id=request_id,
            channel=channel,
            input_hash=input_hash,
            prompt_version=prompt_version_label,
            outcome=outcome_label,
            raw_output=raw_dict,
            latency_ms=latency_ms,
            tokens=tokens,
        )

        # -----------------------------------------------------------------
        # Step 7: Cache successful result
        # -----------------------------------------------------------------
        if llm_output and self.redis:
            try:
                await self.redis.set(
                    cache_key,
                    llm_output.model_dump_json(),
                    ex=settings.llm_cache_ttl_seconds,
                )
            except Exception as cache_write_err:
                logger.debug(
                    "llm_cache_write_error",
                    extra={"error": str(cache_write_err)}
                )

        return llm_output

    async def generate_suggestions(
        self,
        *,
        request_id: str,
        channel: str,
        name_ar: str,
        name_en: str,
        activity_category: Optional[str] = None,
        legal_form: Optional[str] = None,
        num_candidates: int = 25,
        conflict_brand: Optional[str] = None,
    ) -> Optional[SuggestionBatchOutput]:
        """
        Stage ⑥: Generate ~25 candidate trade name pairs using suggestions LLM model (F8, F9, N8).
        """
        from llm.prompts import (
            DEFAULT_SUGGESTIONS_SYSTEM_PROMPT,
            build_suggestions_user_message,
        )

        input_hash = compute_input_hash(
            normalized_ar=name_ar,
            normalized_en=name_en,
            legal_form=legal_form,
        )

        if not _circuit_breaker.is_available():
            logger.warning("llm_circuit_open_suggestions_skip", extra={"request_id": request_id})
            await self._write_audit(
                request_id=request_id,
                channel=channel,
                input_hash=input_hash,
                prompt_version="suggestions_v1",
                outcome="circuit_open",
                raw_output=None,
                latency_ms=None,
                tokens=None,
            )
            return None

        user_message = build_suggestions_user_message(
            name_ar=name_ar,
            name_en=name_en,
            activity_category=activity_category,
            legal_form=legal_form,
            num_candidates=num_candidates,
            conflict_brand=conflict_brand,
        )

        cfg = get_settings()
        payload = {
            "model": cfg.effective_suggestions_model,
            "messages": [
                {"role": "system", "content": DEFAULT_SUGGESTIONS_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.7,   # Suggestions benefit from creative diversity
            "max_tokens": 450,
            "response_format": _format_response_format(SuggestionBatchOutput.model_json_schema()),
        }

        output: Optional[SuggestionBatchOutput] = None
        latency_ms = None
        tokens = None
        raw_dict = None
        outcome_label = "error"

        for attempt in range(settings.llm_max_retries + 1):
            start_time = time.monotonic()
            try:
                response = await self._http_client.post("/chat/completions", json=payload)
                latency_ms = int((time.monotonic() - start_time) * 1000)

                if response.status_code >= 500:
                    if attempt < settings.llm_max_retries:
                        await asyncio.sleep(0.1 * (attempt + 1))
                        continue
                    outcome_label = "server_error"
                    _circuit_breaker.record_failure()
                    break

                if response.status_code != 200:
                    outcome_label = f"http_{response.status_code}"
                    _circuit_breaker.record_failure()
                    break

                resp_json = response.json()
                usage = resp_json.get("usage", {})
                tokens = usage.get("total_tokens")
                content = resp_json["choices"][0]["message"]["content"]
                raw_dict = json.loads(content)

                output = SuggestionBatchOutput.model_validate(raw_dict)
                outcome_label = "success"
                _circuit_breaker.record_success()
                break

            except (ValidationError, json.JSONDecodeError, KeyError) as schema_err:
                logger.warning("suggestions_schema_error", extra={"error": str(schema_err)})
                outcome_label = "schema_error"
                _circuit_breaker.record_failure()
                break

            except httpx.TimeoutException:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                if attempt < settings.llm_max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                outcome_label = "timeout"
                _circuit_breaker.record_failure()
                break

            except (httpx.RequestError, httpx.ConnectError):
                latency_ms = int((time.monotonic() - start_time) * 1000)
                if attempt < settings.llm_max_retries:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                outcome_label = "connection_error"
                _circuit_breaker.record_failure()
                break

        await self._write_audit(
            request_id=request_id,
            channel=channel,
            input_hash=input_hash,
            prompt_version="suggestions_v1",
            outcome=outcome_label,
            raw_output=raw_dict,
            latency_ms=latency_ms,
            tokens=tokens,
        )

        return output

    async def check_transliteration(
        self,
        *,
        request_id: str,
        channel: str,
        name_ar: str,
        name_en: str,
        original_ar: Optional[str] = None,
        original_en: Optional[str] = None,
    ) -> Optional[TransliterationCheckOutput]:
        """
        Validate transliteration consistency between Arabic and English forms (F7).
        """
        from llm.prompts import (
            DEFAULT_TRANSLITERATION_SYSTEM_PROMPT,
            build_transliteration_user_message,
        )

        input_hash = compute_input_hash(normalized_ar=name_ar, normalized_en=name_en)

        if not _circuit_breaker.is_available():
            return None

        user_message = build_transliteration_user_message(
            name_ar=name_ar,
            name_en=name_en,
            original_ar=original_ar,
            original_en=original_en,
        )

        cfg = get_settings()
        payload = {
            "model": cfg.effective_analyzer_model,
            "messages": [
                {"role": "system", "content": DEFAULT_TRANSLITERATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0,
            "max_tokens": 512,
            "response_format": _format_response_format(TransliterationCheckOutput.model_json_schema()),
        }

        output: Optional[TransliterationCheckOutput] = None
        latency_ms = None
        tokens = None
        raw_dict = None
        outcome_label = "error"

        try:
            start_time = time.monotonic()
            response = await self._http_client.post("/chat/completions", json=payload)
            latency_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code == 200:
                resp_json = response.json()
                usage = resp_json.get("usage", {})
                tokens = usage.get("total_tokens")
                content = resp_json["choices"][0]["message"]["content"]
                raw_dict = json.loads(content)
                output = TransliterationCheckOutput.model_validate(raw_dict)
                outcome_label = "success"
                _circuit_breaker.record_success()
            else:
                outcome_label = f"http_{response.status_code}"
                _circuit_breaker.record_failure()
        except Exception as exc:
            logger.warning("transliteration_check_failed", extra={"error": str(exc)})
            outcome_label = "error"
            _circuit_breaker.record_failure()

        await self._write_audit(
            request_id=request_id,
            channel=channel,
            input_hash=input_hash,
            prompt_version="transliteration_v1",
            outcome=outcome_label,
            raw_output=raw_dict,
            latency_ms=latency_ms,
            tokens=tokens,
        )

        return output

    async def transliterate_to_arabic(
        self,
        name_en: str,
        request_id: Optional[str] = None,
        channel: str = "online",
    ) -> Optional[dict[str, Any]]:
        """
        Transliterate English trade name to official DED Arabic trade name.
        Uses LLM with fast fallback.
        """
        import uuid
        from llm.prompts import DEFAULT_TRANSLITERATE_TO_ARABIC_PROMPT

        clean_en = (name_en or "").strip()
        if not clean_en:
            return {"arabic_name": "", "confidence": 1.0}

        req_id = request_id or f"translit-{uuid.uuid4().hex[:8]}"

        if not _circuit_breaker.is_available():
            return None

        cfg = get_settings()
        payload = {
            "model": cfg.effective_analyzer_model,
            "messages": [
                {"role": "system", "content": DEFAULT_TRANSLITERATE_TO_ARABIC_PROMPT},
                {"role": "user", "content": f"English Trade Name: {clean_en}"},
            ],
            "temperature": 0,
            "max_tokens": 128,
            "response_format": {"type": "json_object"},
        }

        try:
            response = await self._http_client.post("/chat/completions", json=payload)
            if response.status_code == 200:
                resp_json = response.json()
                content = resp_json["choices"][0]["message"]["content"]
                raw_dict = json.loads(content)
                _circuit_breaker.record_success()
                return {
                    "arabic_name": raw_dict.get("arabic_name", ""),
                    "confidence": float(raw_dict.get("confidence", 0.95)),
                }
            else:
                _circuit_breaker.record_failure()
                return None
        except Exception as exc:
            logger.warning("llm_transliterate_to_arabic_failed", extra={"error": str(exc)})
            _circuit_breaker.record_failure()
            return None

    async def transliterate_to_english(
        self,
        name_ar: str,
        request_id: Optional[str] = None,
        channel: str = "online",
    ) -> Optional[dict[str, Any]]:
        """
        Transliterate Arabic trade name to official DED English trade name.
        Uses LLM with fast fallback.
        """
        import uuid
        from llm.prompts import DEFAULT_TRANSLITERATE_TO_ENGLISH_PROMPT

        clean_ar = (name_ar or "").strip()
        if not clean_ar:
            return {"english_name": "", "confidence": 1.0}

        req_id = request_id or f"translit-ar2en-{uuid.uuid4().hex[:8]}"

        if not _circuit_breaker.is_available():
            return None

        cfg = get_settings()
        payload = {
            "model": cfg.effective_analyzer_model,
            "messages": [
                {"role": "system", "content": DEFAULT_TRANSLITERATE_TO_ENGLISH_PROMPT},
                {"role": "user", "content": f"Arabic Trade Name: {clean_ar}"},
            ],
            "temperature": 0,
            "max_tokens": 128,
            "response_format": {"type": "json_object"},
        }

        try:
            response = await self._http_client.post("/chat/completions", json=payload)
            if response.status_code == 200:
                resp_json = response.json()
                content = resp_json["choices"][0]["message"]["content"]
                raw_dict = json.loads(content)
                _circuit_breaker.record_success()
                return {
                    "english_name": raw_dict.get("english_name") or raw_dict.get("name_en", ""),
                    "confidence": float(raw_dict.get("confidence", 0.95)),
                }
            else:
                _circuit_breaker.record_failure()
                return None
        except Exception as exc:
            logger.warning("llm_transliterate_to_english_failed", extra={"error": str(exc)})
            _circuit_breaker.record_failure()
            return None

    async def suggest_category(
        self,
        *,
        request_id: str,
        channel: str,
        name_ar: str,
        name_en: str,
        activity_type: Optional[str] = None,
        user_context: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Suggest activity category based on trade name and entered activity, detecting mismatches (E6).
        """
        from llm.prompts import (
            DEFAULT_CATEGORY_SYSTEM_PROMPT,
            build_category_user_message,
        )

        input_hash = compute_input_hash(normalized_ar=name_ar, normalized_en=name_en)

        if not _circuit_breaker.is_available():
            return None

        user_message = build_category_user_message(
            name_ar=name_ar,
            name_en=name_en,
            activity_type=activity_type,
            user_context=user_context,
        )

        cfg = get_settings()
        payload = {
            "model": cfg.effective_analyzer_model,
            "messages": [
                {"role": "system", "content": DEFAULT_CATEGORY_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
        }

        output: Optional[dict[str, Any]] = None
        latency_ms = None
        tokens = None
        raw_dict = None
        outcome_label = "error"

        try:
            start_time = time.monotonic()
            response = await self._http_client.post("/chat/completions", json=payload)
            latency_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code == 200:
                resp_json = response.json()
                usage = resp_json.get("usage", {})
                tokens = usage.get("total_tokens")
                content = resp_json["choices"][0]["message"]["content"]
                raw_dict = json.loads(content)
                output = raw_dict
                outcome_label = "success"
                _circuit_breaker.record_success()
            else:
                outcome_label = f"http_{response.status_code}"
                _circuit_breaker.record_failure()
        except Exception as exc:
            logger.warning("category_suggestion_failed", extra={"error": str(exc)})
            outcome_label = "error"
            _circuit_breaker.record_failure()

        await self._write_audit(
            request_id=request_id,
            channel=channel,
            input_hash=input_hash,
            prompt_version="category_v2",
            outcome=outcome_label,
            raw_output=raw_dict,
            latency_ms=latency_ms,
            tokens=tokens,
        )

        return output

    async def generate_brief(
        self,
        *,
        request_id: str,
        channel: str,
        name_ar: str,
        name_en: str,
        decision: str,
        flags: Optional[list[dict]] = None,
        similar_names: Optional[list[dict]] = None,
        activity_fit: Optional[dict] = None,
        transliteration: Optional[dict] = None,
    ) -> Optional[ReviewerBriefOutput]:
        """
        Stage ⑧: Generate DED Reviewer Copilot brief using LLM analyzer model (E5, N8).
        """
        from llm.prompts import (
            DEFAULT_BRIEF_SYSTEM_PROMPT,
            build_brief_user_message,
        )

        input_hash = compute_input_hash(normalized_ar=name_ar, normalized_en=name_en)

        if not _circuit_breaker.is_available():
            return None

        user_message = build_brief_user_message(
            name_ar=name_ar,
            name_en=name_en,
            decision=decision,
            flags=flags,
            similar_names=similar_names,
            activity_fit=activity_fit,
            transliteration=transliteration,
        )

        cfg = get_settings()
        payload = {
            "model": cfg.effective_analyzer_model,
            "messages": [
                {"role": "system", "content": DEFAULT_BRIEF_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
            "response_format": _format_response_format(ReviewerBriefOutput.model_json_schema()),
        }

        output: Optional[ReviewerBriefOutput] = None
        latency_ms = None
        tokens = None
        raw_dict = None
        outcome_label = "error"

        try:
            start_time = time.monotonic()
            response = await self._http_client.post("/chat/completions", json=payload)
            latency_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code == 200:
                resp_json = response.json()
                usage = resp_json.get("usage", {})
                tokens = usage.get("total_tokens")
                content = resp_json["choices"][0]["message"]["content"]
                raw_dict = json.loads(content)
                output = ReviewerBriefOutput.model_validate(raw_dict)
                outcome_label = "success"
                _circuit_breaker.record_success()
            else:
                outcome_label = f"http_{response.status_code}"
                _circuit_breaker.record_failure()
        except Exception as exc:
            logger.warning("generate_brief_failed", extra={"error": str(exc)})
            outcome_label = "error"
            _circuit_breaker.record_failure()

        await self._write_audit(
            request_id=request_id,
            channel=channel,
            input_hash=input_hash,
            prompt_version="reviewer_brief_v1",
            outcome=outcome_label,
            raw_output=raw_dict,
            latency_ms=latency_ms,
            tokens=tokens,
        )

        return output

    async def generate_lexicon_variants(
        self,
        *,
        request_id: str,
        term: str,
        category: str,
        lang: str,
        channel: str = "online",
    ) -> Optional[LexiconVariantsOutput]:
        """
        Stage ⑨: Generate evasion, phonetic, and Arabizi variants for a compliance term (E7).
        """
        from llm.prompts import (
            DEFAULT_LEXICON_VARIANTS_SYSTEM_PROMPT,
            build_lexicon_variants_user_message,
        )

        input_hash = hashlib.sha256(f"{term}:{category}:{lang}".encode("utf-8")).hexdigest()

        if not _circuit_breaker.is_available():
            return None

        user_message = build_lexicon_variants_user_message(term=term, category=category, lang=lang)

        cfg = get_settings()
        payload = {
            "model": cfg.effective_analyzer_model,
            "messages": [
                {"role": "system", "content": DEFAULT_LEXICON_VARIANTS_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
            "response_format": _format_response_format(LexiconVariantsOutput.model_json_schema()),
        }

        output: Optional[LexiconVariantsOutput] = None
        latency_ms = None
        tokens = None
        raw_dict = None
        outcome_label = "error"

        try:
            start_time = time.monotonic()
            response = await self._http_client.post("/chat/completions", json=payload)
            latency_ms = int((time.monotonic() - start_time) * 1000)

            if response.status_code == 200:
                resp_json = response.json()
                usage = resp_json.get("usage", {})
                tokens = usage.get("total_tokens")
                content = resp_json["choices"][0]["message"]["content"]
                raw_dict = json.loads(content)
                output = LexiconVariantsOutput.model_validate(raw_dict)
                outcome_label = "success"
                _circuit_breaker.record_success()
            else:
                outcome_label = f"http_{response.status_code}"
                _circuit_breaker.record_failure()
        except Exception as exc:
            logger.warning("generate_lexicon_variants_failed", extra={"error": str(exc)})
            outcome_label = "error"
            _circuit_breaker.record_failure()

        await self._write_audit(
            request_id=request_id,
            channel=channel,
            input_hash=input_hash,
            prompt_version="lexicon_variants_v1",
            outcome=outcome_label,
            raw_output=raw_dict,
            latency_ms=latency_ms,
            tokens=tokens,
        )

        return output

    async def _write_audit(
        self,
        request_id: str,
        channel: str,
        input_hash: str,
        prompt_version: str,
        outcome: str,
        raw_output: Optional[dict],
        latency_ms: Optional[int],
        tokens: Optional[int],
    ) -> None:
        """Persist an audit entry independently of the request's database transaction."""
        from db.session import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as audit_session:
                await AuditRepository(audit_session).record_audit(
                    request_id=request_id,
                    channel=channel,
                    input_hash=input_hash,
                    prompt_version=prompt_version,
                    model_id=settings.effective_analyzer_model,
                    outcome=outcome,
                    raw_output=raw_output,
                    latency_ms=latency_ms,
                    tokens=tokens,
                )
                await audit_session.commit()
        except Exception:
            logger.exception(
                "llm_audit_write_failed",
                extra={"request_id": request_id, "outcome": outcome},
            )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http_client.aclose()
