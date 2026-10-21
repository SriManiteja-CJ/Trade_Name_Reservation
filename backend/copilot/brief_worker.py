"""
copilot/brief_worker.py
Stage ⑧ Reviewer Copilot Worker for DED Reviewers (Phase 4).

Responsibilities:
  - Synthesize validation signals (flags, similarity, activity fit, transliteration)
  - Generate official recommendation (approve | reject | return | ssp_committee)
  - Generate draft AdminComments in Arabic and English (LLM or deterministic fallback)
  - Persist brief to ReviewerBrief table
  - Record reviewer decisions for the N7 feedback loop

Spec references:
  E5  — Reviewer copilot brief per submission
  F20 — Support reviewer actions: approve, reject, return, ssp_committee
  N7  — Quality feedback loop from reviewer decisions
  N8  — Bounded cost: single LLM call or deterministic fallback
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import FlagMode, get_settings
from db.models import ReviewerBrief
from llm.gateway import LlmGateway

logger = logging.getLogger(__name__)
settings = get_settings()


class ReviewerCopilotService:
    """
    Stage ⑧ Reviewer Copilot service.
    Generates briefs and records human reviewer decisions.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate_brief(
        self,
        *,
        request_id: str,
        name_ar: str,
        name_en: str,
        decision: str,
        flags: list[dict],
        similar_names: list[dict],
        activity_fit: Optional[dict] = None,
        transliteration: Optional[dict] = None,
        channel: str = "online",
    ) -> ReviewerBrief:
        """
        Produce a ReviewerBrief row for the given validation submission.
        """
        recommendation = "approve"
        draft_comments_en = "Trade name satisfies all DED requirements. No conflicting active names found."
        draft_comments_ar = "الاسم التجاري يستوفي جميع الشروط المحددة بدائرة التنمية الاقتصادية بأم القيوين."

        # -------------------------------------------------------------
        # 1. Deterministic Baseline Recommendation
        # -------------------------------------------------------------
        if decision == "BLOCKED":
            recommendation = "reject"
            reasons_text = "; ".join(f.get("reason_en", "") for f in flags) if flags else "Policy violation"
            draft_comments_en = f"Trade name submission rejected. Issues identified: {reasons_text}."
            draft_comments_ar = "تم رفض الاسم التجاري نظراً لمخالفته ضوابط التسمية المعتمدة."
        elif decision == "NEEDS_REVIEW":
            has_location = any(f.get("category") == "location" for f in flags)
            has_special = any(f.get("category") in ("special", "divine_name") for f in flags)
            if has_location or has_special:
                recommendation = "ssp_committee"
                draft_comments_en = "Submission requires review by the Special Scrutiny Panel (SSP) committee."
                draft_comments_ar = "تتطلب المعاملة عرضاً على لجنة التدقيق الخاصة (SSP) لاتخاذ القرار المناسب."
            else:
                recommendation = "return"
                draft_comments_en = "Trade name returned for applicant amendment. Please review the highlighted issues."
                draft_comments_ar = "تمت إعادة الطلب للمتعامل لإجراء التعديلات المطلوبة وفق الملاحظات."

        # -------------------------------------------------------------
        # 2. LLM Synthesis when ai_reviewer_brief != off
        # -------------------------------------------------------------
        if settings.ai_reviewer_brief != FlagMode.off:
            try:
                gateway = LlmGateway(session=self.session)
                llm_brief = await gateway.generate_brief(
                    request_id=request_id,
                    channel=channel,
                    name_ar=name_ar,
                    name_en=name_en,
                    decision=decision,
                    flags=flags,
                    similar_names=similar_names,
                    activity_fit=activity_fit,
                    transliteration=transliteration,
                )
                await gateway.close()

                if llm_brief:
                    recommendation = llm_brief.recommendation
                    draft_comments_en = llm_brief.draft_admin_comments_en
                    draft_comments_ar = llm_brief.draft_admin_comments_ar
            except Exception as exc:
                logger.warning("copilot_llm_brief_failed_fallback", extra={"error": str(exc)})

        # -------------------------------------------------------------
        # 3. Assemble and Persist Brief
        # -------------------------------------------------------------
        brief_data = {
            "request_id": request_id,
            "name_ar": name_ar,
            "name_en": name_en,
            "decision": decision,
            "recommendation": recommendation,
            "draft_admin_comments_en": draft_comments_en,
            "draft_admin_comments_ar": draft_comments_ar,
            "flags": flags,
            "top_similar": similar_names[:5],
            "activity_fit": activity_fit,
            "transliteration": transliteration,
            "generated_on": datetime.now(timezone.utc).isoformat(),
        }

        # Check existing row
        stmt = select(ReviewerBrief).where(ReviewerBrief.request_id == request_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.brief_json = brief_data
            existing.generated_on = datetime.now(timezone.utc)
            brief_obj = existing
        else:
            brief_obj = ReviewerBrief(
                request_id=request_id,
                brief_json=brief_data,
                generated_on=datetime.now(timezone.utc),
            )
            self.session.add(brief_obj)

        await self.session.commit()
        return brief_obj

    async def get_brief(self, request_id: str) -> Optional[ReviewerBrief]:
        """Retrieve stored brief by request_id."""
        stmt = select(ReviewerBrief).where(ReviewerBrief.request_id == request_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def record_decision(
        self,
        request_id: str,
        decision: str,
    ) -> Optional[ReviewerBrief]:
        """
        Record reviewer action for the N7 feedback loop.
        decision: "approve" | "reject" | "return" | "ssp_committee"
        """
        stmt = select(ReviewerBrief).where(ReviewerBrief.request_id == request_id)
        res = await self.session.execute(stmt)
        brief = res.scalar_one_or_none()

        if brief:
            brief.reviewer_decision = decision
            await self.session.commit()
            logger.info(
                "reviewer_decision_recorded",
                extra={"request_id": request_id, "decision": decision}
            )
            return brief
        return None
