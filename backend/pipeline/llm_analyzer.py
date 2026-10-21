"""
pipeline/llm_analyzer.py
Stage ④ — LLM Analyzer (Phase 2.5)

Builds the analyzer prompt and invokes the LlmGateway. Returns the structured
LlmAnalyzerOutput or None if the LLM is unavailable. In shadow mode, this output
is logged to AiDecisionAudit but does NOT affect the final decision (Stage ⑤ handles
that based on the ai_analyzer feature flag).

Shadow mode contract (F16):
  - ai_analyzer = off    → Stage ④ is skipped entirely; llm_output=None passed to Stage ⑤
  - ai_analyzer = shadow → Stage ④ runs; result is logged but Stage ⑤ uses llm_output=None
                           for the outcome (shadow: "log only, do not affect outcome")
  - ai_analyzer = on     → Stage ④ runs; result is passed to Stage ⑤ and affects outcome

Spec references:
  §3   — Stage ④ description
  §4.2 — LLM output schema
  §6.2 — Timeout, retry, circuit breaker
  F16  — Feature flags (off/shadow/on)
  N1   — LLM unavailable → fail closed
  N5   — No external LLM calls; all calls to internal vLLM
  N6   — Only name pair + category + legal form sent to LLM; no PII
"""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import FlagMode, get_settings
from llm.gateway import LlmGateway
from llm.prompts import get_active_prompt
from llm.schemas import LlmAnalyzerOutput

logger = logging.getLogger(__name__)
settings = get_settings()

# Default prompt name — matches the row seeded by llm/prompts.py
ANALYZER_PROMPT_NAME = "analyzer_v1"


async def run_llm_analyzer(
    *,
    request_id: str,
    channel: str,
    name_ar: str,
    name_en: str,
    normalized_ar: str,
    normalized_en: str,
    activity_category: Optional[str] = None,
    legal_form: Optional[str] = None,
    similar_names: Optional[list[dict]] = None,
    session: AsyncSession,
    redis_client=None,
) -> Optional[LlmAnalyzerOutput]:
    """
    Run Stage ④ — LLM Analyzer.

    Behaviour depends on the ai_analyzer feature flag:
      off    → returns None immediately (no call made)
      shadow → makes the call, logs result to audit, but caller must use None
               as the effective llm_output for Stage ⑤
      on     → makes the call, returns result for Stage ⑤ to use

    Callers (the route handler) are responsible for deciding which value to
    pass to apply_policy() based on is_shadow_mode(). This function always
    returns the raw LlmAnalyzerOutput (or None) regardless of mode — the
    caller decides how to use it.

    Args:
        request_id:        DED application request ID (N3)
        channel:           "online" | "walkin"
        name_ar:           Raw Arabic trade name
        name_en:           Raw English trade name
        normalized_ar:     Normalized Arabic form (for cache key)
        normalized_en:     Normalized English form (for cache key)
        activity_category: Declared activity category
        legal_form:        Legal form token
        similar_names:     Top-10 similar names from Stage ③ (list of dicts)
        session:           Async DB session
        redis_client:      aioredis client (optional; None disables response caching)

    Returns:
        LlmAnalyzerOutput if LLM call succeeded, None otherwise.
    """
    current_flag = settings.ai_analyzer

    # Stage ④ is completely skipped when flag = off
    if current_flag == FlagMode.off:
        logger.debug(
            "llm_analyzer_skipped_flag_off",
            extra={"request_id": request_id}
        )
        return None

    # Load the active prompt (Phase 2.3 — prompt versioning)
    prompt = await get_active_prompt(name=ANALYZER_PROMPT_NAME, session=session)

    # Build and call the gateway
    gateway = LlmGateway(session=session, redis_client=redis_client)
    try:
        result = await gateway.analyze(
            request_id=request_id,
            channel=channel,
            name_ar=name_ar,
            name_en=name_en,
            normalized_ar=normalized_ar,
            normalized_en=normalized_en,
            activity_category=activity_category,
            legal_form=legal_form,
            similar_names=similar_names,
            system_prompt=prompt.text,
            prompt_version_label=prompt.version_label,
        )

        if result is not None:
            logger.info(
                "llm_analyzer_success",
                extra={
                    "request_id": request_id,
                    "flag_mode": current_flag.value,
                    "risks_count": len(result.risks),
                    "transliteration_consistent": result.transliteration.consistent,
                }
            )
        else:
            logger.warning(
                "llm_analyzer_returned_none",
                extra={"request_id": request_id, "flag_mode": current_flag.value}
            )

        return result

    except Exception as exc:
        logger.error(
            "llm_analyzer_unexpected_error",
            extra={"request_id": request_id, "error": str(exc)}
        )
        return None
    finally:
        await gateway.close()
