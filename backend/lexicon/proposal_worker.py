"""
lexicon/proposal_worker.py
Stage ⑨ Lexicon Manager & Proposal Worker (Phase 5, E7).

Responsibilities:
  - Generate phonetic, spelling, typo, and Arabizi variants for compliance terms
  - Uses vLLM LLM gateway when ai_analyzer != off
  - Deterministic algorithmic fallback when LLM is unavailable / flag is off
  - Enforces Human-in-the-Loop review: all proposed variants are held in pending
    status (approved_by is NULL) until explicit human admin approval (E7).
  - Admin approval updates approved_by to the reviewer name, activating the term.

Spec references:
  E7  — LLM-proposed lexicon variants, human-approved before entering lexicon
  F4  — Word checks (prohibited, profanity, unfriendly, special, divine_name, location, family_name)
  §5.2 — POST Admin/Lexicon/Proposals
"""
import logging
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import FlagMode, get_settings
from db.models import Lexicon
from llm.gateway import LlmGateway
from pipeline.normalizer import normalize_arabic, normalize_english

logger = logging.getLogger(__name__)
settings = get_settings()


class LexiconProposalWorker:
    """
    Stage ⑨ Lexicon Proposal Worker.
    Proposes evasion and phonetic variants for compliance screening.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate_variants(
        self,
        *,
        term: str,
        category: str,
        lang: str,
        channel: str = "online",
        request_id: str = "lexicon-proposal",
    ) -> list[str]:
        """
        Generate candidate spelling and evasion variants for a root term.
        Tries LLM gateway first; falls back to deterministic rule-based generator.
        """
        variants: set[str] = set()

        # 1. Attempt LLM generation when ai_analyzer != off
        if settings.ai_analyzer != FlagMode.off:
            try:
                gateway = LlmGateway(session=self.session)
                llm_output = await gateway.generate_lexicon_variants(
                    request_id=request_id,
                    term=term,
                    category=category,
                    lang=lang,
                    channel=channel,
                )
                await gateway.close()

                if llm_output and llm_output.variants:
                    for v in llm_output.variants:
                        clean_v = v.strip().lower()
                        if clean_v and clean_v != term.strip().lower():
                            variants.add(clean_v)
            except Exception as exc:
                logger.warning(
                    "llm_lexicon_variants_failed_falling_back",
                    extra={"error": str(exc), "term": term}
                )

        # 2. Always supplement with or fallback to deterministic algorithmic variants
        det_variants = self.generate_deterministic_variants(term=term, lang=lang)
        variants.update(det_variants)

        # Remove the exact original term from variants
        clean_original = term.strip().lower()
        variants.discard(clean_original)

        return sorted(variants)

    @staticmethod
    def generate_deterministic_variants(term: str, lang: str) -> list[str]:
        """
        Deterministic algorithmic generation of phonetic and evasion variants:
        - Common letter substitutions (k/c/q, s/z, ph/f, i/y)
        - Arabizi number substitutions (7=ح, 3=ع, 5=خ, 2=ء)
        - Letter doubling and common typo permutations
        """
        results: set[str] = set()
        clean = term.strip().lower()

        if not clean:
            return []

        # English / Latin substitutions
        if lang in ("en", "both") or not re.search(r"[\u0600-\u06FF]", clean):
            # c <-> k <-> q
            if "c" in clean:
                results.add(clean.replace("c", "k"))
                results.add(clean.replace("c", "q"))
            if "k" in clean:
                results.add(clean.replace("k", "c"))
                results.add(clean.replace("k", "q"))
            if "q" in clean:
                results.add(clean.replace("q", "k"))
                results.add(clean.replace("q", "c"))

            # s <-> z
            if "s" in clean:
                results.add(clean.replace("s", "z"))
            if "z" in clean:
                results.add(clean.replace("z", "s"))

            # ph <-> f
            if "ph" in clean:
                results.add(clean.replace("ph", "f"))
            if "f" in clean:
                results.add(clean.replace("f", "ph"))

            # i <-> y
            if "i" in clean:
                results.add(clean.replace("i", "y"))
            if "y" in clean:
                results.add(clean.replace("y", "i"))

            # Arabizi / Leetspeak digits
            # e -> 3, o -> 0, a -> 4, i -> 1, s -> 5
            leet = clean
            for old_char, new_num in [("e", "3"), ("o", "0"), ("a", "4"), ("i", "1"), ("s", "5")]:
                if old_char in clean:
                    results.add(clean.replace(old_char, new_num))

        # Arabic substitutions & Arabizi mapping
        if lang in ("ar", "both") or re.search(r"[\u0600-\u06FF]", clean):
            # Common Arabic spelling variations
            if "ة" in clean:
                results.add(clean.replace("ة", "ه"))
            if "ه" in clean and clean.endswith("ه"):
                results.add(clean[:-1] + "ة")
            if "ي" in clean and clean.endswith("ي"):
                results.add(clean[:-1] + "ى")
            if "ى" in clean and clean.endswith("ى"):
                results.add(clean[:-1] + "ي")
            if "أ" in clean or "إ" in clean or "آ" in clean:
                results.add(re.sub(r"[أإآ]", "ا", clean))

            # Arabizi transcriptions (Arabic to Latin numbers)
            arabizi_map = {
                "ح": "7", "ع": "3", "خ": "5", "غ": "8",
                "ط": "6", "ص": "9", "ء": "2", "أ": "2", "إ": "2",
                "ق": "9", "ش": "sh", "ث": "th", "ذ": "th",
            }
            has_arabizi = False
            arabizi_variant = clean
            for ar_char, num in arabizi_map.items():
                if ar_char in arabizi_variant:
                    arabizi_variant = arabizi_variant.replace(ar_char, num)
                    has_arabizi = True
            if has_arabizi:
                results.add(arabizi_variant)

        # Letter doubling (e.g. bet -> bett, casino -> cassino)
        for i in range(len(clean)):
            if clean[i].isalpha():
                doubled = clean[:i] + clean[i] + clean[i:]
                results.add(doubled)
                break

        results.discard(clean)
        return sorted(results)

    async def create_term_proposal(
        self,
        *,
        term: str,
        category: str,
        lang: str,
        severity: str = "block",
        custom_variants: Optional[list[str]] = None,
        auto_generate_variants: bool = True,
        approved_by: Optional[str] = None,
    ) -> Lexicon:
        """
        Create a new lexicon entry or pending proposal.
        If auto_generate_variants is True, uses LLM/deterministic generation.
        Holds row in pending status if approved_by is None (E7).
        """
        norm_term = normalize_arabic(term) if lang == "ar" else normalize_english(term)

        all_variants: set[str] = set()
        if custom_variants:
            all_variants.update(str(v).strip().lower() for v in custom_variants if str(v).strip())

        if auto_generate_variants:
            generated = await self.generate_variants(term=term, category=category, lang=lang)
            all_variants.update(generated)

        all_variants.discard(norm_term.lower())
        variants_list = sorted(all_variants)

        # Check existing row
        stmt = select(Lexicon).where(
            Lexicon.normalized_term == norm_term,
            Lexicon.category == category,
            Lexicon.lang == lang,
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            # Merge variants
            old_vars = set(existing.variants or [])
            old_vars.update(variants_list)
            existing.variants = sorted(old_vars)
            existing.severity = severity
            if approved_by is not None:
                existing.approved_by = approved_by
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        new_entry = Lexicon(
            term=term,
            normalized_term=norm_term,
            category=category,
            lang=lang,
            severity=severity,
            variants=variants_list,
            approved_by=approved_by,
        )
        self.session.add(new_entry)
        await self.session.flush()
        await self.session.refresh(new_entry)
        return new_entry

    async def approve_proposal(
        self,
        proposal_id: int,
        reviewer: str,
    ) -> Optional[Lexicon]:
        """
        Approve a pending lexicon proposal (F4, E7).
        Sets approved_by to the reviewer's ID/name.
        """
        stmt = select(Lexicon).where(Lexicon.id == proposal_id)
        res = await self.session.execute(stmt)
        entry = res.scalar_one_or_none()

        if not entry:
            return None

        entry.approved_by = reviewer
        await self.session.flush()
        await self.session.refresh(entry)
        logger.info(
            "lexicon_proposal_approved",
            extra={"proposal_id": proposal_id, "reviewer": reviewer, "term": entry.term}
        )
        return entry

    async def reject_proposal(
        self,
        proposal_id: int,
    ) -> Optional[dict]:
        """
        Reject a pending proposal (removes from active queue).
        """
        stmt = select(Lexicon).where(Lexicon.id == proposal_id)
        res = await self.session.execute(stmt)
        entry = res.scalar_one_or_none()

        if not entry:
            return None

        info = {
            "id": entry.id,
            "term": entry.term,
            "category": entry.category,
            "lang": entry.lang,
            "variants": entry.variants,
        }

        await self.session.delete(entry)
        await self.session.flush()
        logger.info("lexicon_proposal_rejected", extra={"proposal_id": proposal_id})
        return info
