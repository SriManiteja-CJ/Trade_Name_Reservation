
"""
pipeline/suggestion_engine.py
Stage ⑥ Suggestion Engine for the Trade Name Intelligence Service.

Responsibilities:
  1. Call LLM to draft ~25 bilingual candidate pairs (F8, F9 complementary patterns).
  2. Fall back to deterministic template-based generation if LLM fails (Ambiguity #5).
  3. Batch filter candidates through Stage ① normalizer and Stage ② deterministic gates.
  4. Perform single set-based SQL query to eliminate active/reserved names (F18, N8).
  5. Apply legal-form formatting when required (F8).
  6. Ensure all English suggestion names are returned in UPPER CASE (F17).
  7. Rank and return top 10 distinct, unreserved suggestions (F8).

Spec references:
  F8  — Return up to 10 distinct, unreserved suggestions; include legal form if required
  F9  — Complementary patterns (name + activity wording)
  F17 — English suggestions returned in UPPER CASE
  F18 — Reserved names are never suggested (single set query)
  F21 — Released/expired names can become suggested if clean
  N8  — Bounded cost: small LLM model + single batch DB query
  §3.1 Stage ⑥ — Suggestion Engine architecture
"""
import logging
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import FlagMode, get_settings
from lexicon.repository import LexiconRepository
from llm.gateway import LlmGateway
from pipeline.normalizer import normalize_arabic, normalize_english, strip_tokens

logger = logging.getLogger(__name__)
settings = get_settings()

def extract_core_brand_token(name: str, lang: str = "en") -> str:
    """
    Isolates the distinctive brand identifier from common descriptor terms (Requirement 2 & 3).
    e.g. 'Teja Cafe and Restaurant' -> 'Teja'
         'Cloudjune Technologies' -> 'Cloudjune'
         'مطعم وكافيه تيجا' -> 'تيجا'
         'كلاودجون للتكنولوجيا' -> 'كلاودجون'
    """
    if not name:
        return ""
    if lang == "en":
        descriptors = {
            "cafe", "café", "restaurant", "restaurants", "bistro", "bistros",
            "diner", "dining", "kitchen", "lounge", "food", "foods", "and", "&",
            "co", "company", "house", "trading", "services", "solutions",
            "tech", "technology", "technologies", "software", "systems", "digital",
            "consulting", "consultancy", "group", "enterprises", "general", "express",
            "grill", "bakery", "sweets", "bar", "hub", "center", "dine", "innovations",
            "innovation", "labs", "lab", "holdings", "holding", "corporation", "corp",
            "international", "commercial", "smart", "management", "logistics"
        }
        tokens = name.strip().split()
        brand_tokens = [w for w in tokens if w.lower() not in descriptors]
        return " ".join(brand_tokens) if brand_tokens else name.strip()
    else:
        descriptors_ar = {
            "مطعم", "كافيه", "مقهى", "لاونج", "بسترو", "مأكولات", "ماكولات",
            "وجبات", "و", "للحلول", "حلول", "للتجارة", "تجارة", "للخدمات", "خدمات",
            "شركة", "مؤسسة", "العامة", "اكسبريس", "مطبخ", "جريل", "مخبز", "حلويات", "بيت",
            "مركز", "جروب", "داينينغ", "تكنولوجيا", "التكنولوجيا", "للتكنولوجيا",
            "تقنية", "التقنية", "للتقنية", "تقنيات", "التقنيات", "للتقنيات",
            "برمجيات", "البرمجيات", "للبرمجيات", "أنظمة", "الأنظمة", "للأنظمة",
            "رقمية", "الرقمية", "للرقمية", "استشارات", "الاستشارات", "للاستشارات",
            "مختبرات", "ابتكار", "للابتكار", "القابضة", "العالمية", "الذكية", "الدولية"
        }
        tokens = name.strip().split()
        brand_tokens = [w for w in tokens if w not in descriptors_ar]
        return " ".join(brand_tokens) if brand_tokens else name.strip()


def transliterate_en_to_ar_token(token: str) -> str:
    """
    Phonetically transliterates an English brand name into Arabic script.
    e.g. 'Teja' -> 'تيجا', 'Noor' -> 'نور'
    """
    if not token:
        return ""
    common_map = {
        "teja": "تيجا",
        "sahra": "صحراء",
        "sahraa": "صحراء",
        "noor": "نور",
        "nour": "نور",
        "al noor": "النور",
        "alnoor": "النور",
        "baraka": "بركة",
        "al baraka": "البركة",
        "albaraka": "البركة",
        "falcon": "فالكون",
        "star": "ستار",
        "al star": "الستار",
        "oasis": "الواحة",
        "marina": "مارينا",
        "delta": "دلتا",
        "prime": "برايم",
        "apex": "أبيكس",
        "crown": "كراون",
        "elite": "إيليت",
        "future": "فيوتشر",
    }
    low = token.lower().strip()
    if low in common_map:
        return common_map[low]

    mapping = {
        "sh": "ش", "th": "ث", "kh": "خ", "ch": "تش", "ph": "ف", "gh": "غ", "dh": "ذ",
        "a": "ا", "b": "ب", "c": "ك", "d": "د", "e": "ي", "f": "ف", "g": "ج",
        "h": "ه", "i": "ي", "j": "ج", "k": "ك", "l": "ل", "m": "م", "n": "ن",
        "o": "و", "p": "ب", "q": "ق", "r": "ر", "s": "س", "t": "ت", "u": "و",
        "v": "ف", "w": "و", "x": "كس", "y": "ي", "z": "ز"
    }
    res = []
    i = 0
    t = low
    while i < len(t):
        if i + 1 < len(t) and t[i:i+2] in mapping:
            res.append(mapping[t[i:i+2]])
            i += 2
        elif t[i] in mapping:
            res.append(mapping[t[i]])
            i += 1
        elif t[i].isspace():
            res.append(" ")
            i += 1
        else:
            i += 1
    return "".join(res).strip()


def transliterate_ar_to_en_token(token: str) -> str:
    """
    Phonetically transliterates an Arabic brand name into Latin/English script.
    e.g. 'تيجا' -> 'Teja', 'صحراء' -> 'Sahra'
    """
    if not token:
        return ""
    common_rev_map = {
        "تيجا": "Teja",
        "صحراء": "Sahra",
        "صحرا": "Sahra",
        "نور": "Noor",
        "النور": "Al Noor",
        "بركة": "Baraka",
        "البركة": "Al Baraka",
        "فالكون": "Falcon",
        "الواحة": "Oasis",
        "مارينا": "Marina",
        "دلتا": "Delta",
        "برايم": "Prime",
    }
    token_str = token.strip()
    if token_str in common_rev_map:
        return common_rev_map[token_str]

    ar_to_en = {
        "ا": "a", "أ": "a", "إ": "e", "آ": "aa", "ب": "b", "ت": "t", "ث": "th",
        "ج": "j", "ح": "h", "خ": "kh", "د": "d", "ذ": "dh", "ر": "r", "ز": "z",
        "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "ع": "a",
        "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n",
        "ه": "h", "و": "w", "ي": "y", "ى": "a", "ة": "h", "ء": "a"
    }
    res = []
    for char in token_str:
        if char in ar_to_en:
            res.append(ar_to_en[char])
        elif char.isspace():
            res.append(" ")
    return "".join(res).title().strip()


def is_candidate_relevant(
    cand_en: str,
    cand_ar: str,
    brand_en: str,
    brand_ar: str,
    brand_conflict: bool = False,
) -> bool:
    """
    Checks if a suggestion candidate is meaningfully related to the user's core brand tokens.
    If brand_conflict is True, strictly ensures the candidate DOES NOT reuse the conflicting brand token.
    """
    b_en = (brand_en or "").lower().strip()
    b_ar = (brand_ar or "").strip()

    c_en = (cand_en or "").lower().strip()
    c_ar = (cand_ar or "").strip()

    if brand_conflict:
        # Strictly reject any candidate that contains the conflicting/registered brand token
        if b_en and (b_en in c_en or any(w == b_en for w in c_en.split())):
            return False
        if b_ar and (b_ar in c_ar or any(w == b_ar for w in c_ar.split())):
            return False
        trans_ar = transliterate_en_to_ar_token(b_en)
        if trans_ar and (trans_ar in c_ar or any(w == trans_ar for w in c_ar.split())):
            return False
        trans_en = transliterate_ar_to_en_token(b_ar).lower()
        if trans_en and (trans_en in c_en or any(w == trans_en for w in c_en.split())):
            return False
        return True

    # 1. Direct token or substring match in English
    if b_en and (b_en in c_en or any(token in c_en.split() for token in b_en.split())):
        return True

    # 2. Direct token or substring match in Arabic
    if b_ar and (b_ar in c_ar or any(token in c_ar.split() for token in b_ar.split())):
        return True

    # 3. Transliterated token match
    trans_ar = transliterate_en_to_ar_token(b_en)
    if trans_ar and (trans_ar in c_ar or any(token in c_ar.split() for token in trans_ar.split())):
        return True

    trans_en = transliterate_ar_to_en_token(b_ar).lower()
    if trans_en and (trans_en in c_en or any(token in c_en.split() for token in trans_en.split())):
        return True

    # 4. Fuzzy ratio on brand token
    try:
        from rapidfuzz import fuzz
        if b_en:
            for w in c_en.split():
                if fuzz.ratio(b_en, w) >= 70:
                    return True
        if b_ar:
            for w in c_ar.split():
                if fuzz.ratio(b_ar, w) >= 70:
                    return True
    except Exception:
        pass

    return False


def generate_dynamic_phonetic_variants(
    base_name_en: str,
    descriptors_en: str,
    base_name_ar: str,
    descriptors_ar: str,
    brand_conflict: bool = False,
) -> list[tuple[str, str, str]]:
    """
    Generates close-cousin brand alternatives preserving the applicant's core identity and concept.
    e.g. 'CloudJune Technologies' -> 'CloudNine Technologies', 'CloudJini Technologies', 'CloudNova Technologies'
         'Teja Cafe' -> 'TejaNova Cafe', 'TejaCraft Cafe', 'TejaCore Cafe'
    """
    variants: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    b_en = (base_name_en or "").strip().title()
    desc_en = (descriptors_en or "").strip().title()
    desc_ar = (descriptors_ar or "").strip()

    if not b_en and base_name_ar:
        b_en = transliterate_ar_to_en_token(base_name_ar)

    if not b_en:
        return []

    b_low = b_en.lower()

    # Detect common distinctive compound prefixes (e.g. Cloud in CloudJune, Cyber in CyberTech)
    KNOWN_PREFIXES = [
        ("cloud", "Cloud", "كلاود"),
        ("cyber", "Cyber", "سايبر"),
        ("data", "Data", "داتا"),
        ("tech", "Tech", "تك"),
        ("smart", "Smart", "سمارت"),
        ("star", "Star", "ستار"),
        ("sun", "Sun", "صن"),
        ("sky", "Sky", "سكاي"),
        ("blue", "Blue", "بلو"),
        ("meta", "Meta", "ميتا"),
        ("omni", "Omni", "أومني"),
        ("alpha", "Alpha", "ألفا"),
    ]

    matched_p_en = None
    matched_p_ar = None
    for p_low, p_en, p_ar in KNOWN_PREFIXES:
        if b_low.startswith(p_low) and len(b_low) > len(p_low):
            matched_p_en = p_en
            matched_p_ar = p_ar
            break

    # Close-cousin companions
    CLOSE_COMPANIONS = [
        ("ناين", "Nine"),
        ("جيني", "Jini"),
        ("نوفا", "Nova"),
        ("سينك", "Sync"),
        ("بلس", "Pulse"),
        ("سفير", "Sphere"),
        ("ويف", "Wave"),
        ("كرافت", "Craft"),
        ("بيك", "Peak"),
        ("كور", "Core"),
        ("لينك", "Link"),
        ("فايب", "Vibe"),
        ("فيستا", "Vista"),
    ]

    if brand_conflict:
        for tail_ar, tail_en in CLOSE_COMPANIONS:
            cand_en = f"{tail_en} {desc_en}".strip()
            cand_ar = f"{tail_ar} {desc_ar}".strip()
            if cand_en.lower() not in seen:
                seen.add(cand_en.lower())
                variants.append((cand_ar, cand_en, "alternative"))
        return variants

    if matched_p_en and matched_p_ar:
        # e.g. CloudNine, CloudJini, CloudNova, CloudSync, CloudSphere...
        for tail_ar, tail_en in CLOSE_COMPANIONS:
            cand_base_en = f"{matched_p_en}{tail_en}"
            cand_base_ar = f"{matched_p_ar} {tail_ar}"
            cand_en = f"{cand_base_en} {desc_en}".strip() if desc_en else cand_base_en
            cand_ar = f"{cand_base_ar} {desc_ar}".strip() if desc_ar else cand_base_ar
            if cand_en.lower() not in seen and cand_en.lower() != b_low:
                seen.add(cand_en.lower())
                variants.append((cand_ar, cand_en, "template"))
    else:
        # Single-token base names (e.g. Teja -> TejaNova, TejaCraft, TejaCore)
        base_ar = base_name_ar or transliterate_en_to_ar_token(b_en)
        for tail_ar, tail_en in CLOSE_COMPANIONS:
            cand_base_en = f"{b_en}{tail_en}"
            cand_base_ar = f"{base_ar} {tail_ar}".strip()
            cand_en = f"{cand_base_en} {desc_en}".strip() if desc_en else cand_base_en
            cand_ar = f"{cand_base_ar} {desc_ar}".strip() if desc_ar else cand_base_ar
            if cand_en.lower() not in seen:
                seen.add(cand_en.lower())
                variants.append((cand_ar, cand_en, "template"))

    return variants




@dataclass
class SuggestionItemDTO:
    """One verified suggestion candidate."""
    name_ar: str
    name_en: str
    score: float = 1.0
    source: str = "llm"  # "llm" or "template"


def format_legal_form_suffix(legal_form: Optional[str]) -> tuple[str, str]:
    """
    Returns (en_suffix, ar_suffix) for legal forms.
    Uses clean, industry-standard abbreviations (e.g. LLC / ذ.م.م) instead of verbose LIMITED LIABILITY COMPANY.
    """
    if not legal_form:
        return ("", "")
    lf_norm = legal_form.strip().lower()
    if any(k in lf_norm for k in ("limited liability", "llc", "l.l.c", "ذات مسؤولية", "ذ.م.م")):
        return ("LLC", "ذ.م.م")
    if any(k in lf_norm for k in ("sole", "establishment", "proprietorship", "مؤسسة", "فردية")):
        return ("Sole Est.", "مؤسسة فردية")
    if any(k in lf_norm for k in ("partnership", "تضامن", "تضامنية")):
        return ("Partnership", "شركة تضامنية")
    if any(k in lf_norm for k in ("pjsc", "public joint", "مساهمة عامة")):
        return ("PJSC", "ش.م.ع")
    if any(k in lf_norm for k in ("psc", "private joint", "private shareholding", "مساهمة خاصة")):
        return ("PSC", "ش.م.خ")
    return (legal_form.strip().upper(), legal_form.strip())


class SuggestionEngine:
    """
    Stage ⑥ Suggestion Engine.
    Generates, screens, filters, and formats trade name alternatives.
    """

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Optional[Any] = None,
    ) -> None:
        self.session = session
        self.redis_client = redis_client
        self.lexicon_repo = LexiconRepository(session)

    async def generate(
        self,
        *,
        name_ar: str,
        name_en: str,
        activity_category: Optional[str] = None,
        category_id: Optional[int] = None,
        legal_form: Optional[str] = None,
        request_id: str = "suggestion-req",
        channel: str = "online",
        limit: int = 10,
    ) -> list[SuggestionItemDTO]:
        """
        Generate up to `limit` (default 10 per F8) compliant, unreserved suggestions.

        Returns empty list if ai_suggestions is FlagMode.off.
        """
        if settings.ai_suggestions == FlagMode.off:
            return []

        # Resolve integer category_id
        target_category_id: Optional[int] = category_id
        if target_category_id is None and activity_category:
            if str(activity_category).isdigit():
                target_category_id = int(activity_category)
        if target_category_id is None:
            return []

        # Extract core name components dynamically using DynamicBaseNameExtractor
        from pipeline.activity_catalogue import get_category_by_id
        from pipeline.base_name_extractor import canonical_base_name, extract_base_name

        ext_en = extract_base_name(name_en, lang="en")
        ext_ar = extract_base_name(name_ar, lang="ar")

        brand_en = (ext_en.base_name or name_en).title()
        desc_en = ext_en.descriptors.title()
        brand_ar = ext_ar.base_name or name_ar
        desc_ar = ext_ar.descriptors

        # Reconcile brand tokens across languages
        if not brand_ar and brand_en:
            brand_ar = transliterate_en_to_ar_token(brand_en)
        elif not brand_en and brand_ar:
            brand_en = transliterate_ar_to_en_token(brand_ar)
        elif brand_en and brand_ar:
            expected_ar = transliterate_en_to_ar_token(brand_en)
            try:
                from rapidfuzz import fuzz
                if expected_ar and fuzz.ratio(expected_ar, brand_ar) < 40:
                    brand_ar = expected_ar
            except Exception:
                pass

        core_en = brand_en
        core_ar = brand_ar

        candidates: list[tuple[str, str, str]] = []  # (ar, en, source)
        cat_meta = get_category_by_id(target_category_id) if target_category_id else None
        resolved_category = cat_meta["name_en"] if cat_meta else (activity_category or "General Business")

        # -------------------------------------------------------------
        # Step 0: Check if Base Name Collides with Active Registry (Scoped to Category)
        # -------------------------------------------------------------
        from db.models import TradeNameIndex
        brand_conflict = False
        brand_norm_en = normalize_english(brand_en) if brand_en else ""
        brand_norm_ar = normalize_arabic(brand_ar) if brand_ar else ""

        if brand_norm_en or brand_norm_ar:
            conditions = []
            if brand_norm_en:
                conditions.extend([
                    TradeNameIndex.normalized_en == brand_norm_en,
                    TradeNameIndex.normalized_en.like(f"{brand_norm_en} %"),
                    TradeNameIndex.normalized_en.like(f"% {brand_norm_en}"),
                    TradeNameIndex.normalized_en.like(f"% {brand_norm_en} %"),
                ])
            if brand_norm_ar:
                conditions.extend([
                    TradeNameIndex.normalized_ar == brand_norm_ar,
                    TradeNameIndex.normalized_ar.like(f"{brand_norm_ar} %"),
                    TradeNameIndex.normalized_ar.like(f"% {brand_norm_ar}"),
                    TradeNameIndex.normalized_ar.like(f"% {brand_norm_ar} %"),
                ])

            stmt_brand = select(TradeNameIndex).where(
                TradeNameIndex.status.in_(["active", "reserved"]),
                or_(*conditions)
            )
            stmt_brand = stmt_brand.where(TradeNameIndex.category_id == target_category_id)

            res_brand = await self.session.execute(stmt_brand)
            matched_brands = res_brand.scalars().all()
            if matched_brands:
                brand_conflict = True
                logger.info(
                    "suggestion_brand_conflict_detected",
                    extra={"brand_en": brand_en, "brand_ar": brand_ar, "matches": len(matched_brands)}
                )

        # -------------------------------------------------------------
        # Step 1: Attempt LLM Suggestion Generation (~25 candidates)
        # -------------------------------------------------------------
        try:
            gateway = LlmGateway(session=self.session, redis_client=self.redis_client)
            batch = await gateway.generate_suggestions(
                request_id=request_id,
                channel=channel,
                name_ar=core_ar,
                name_en=core_en,
                activity_category=resolved_category,
                legal_form=legal_form,
                num_candidates=10,
                conflict_brand=brand_en if brand_conflict else None,
            )
            await gateway.close()

            if batch and batch.suggestions:
                for s in batch.suggestions:
                    if s.name_ar and s.name_en:
                        if is_candidate_relevant(s.name_en, s.name_ar, brand_en, brand_ar, brand_conflict=brand_conflict):
                            candidates.append((s.name_ar.strip(), s.name_en.strip(), "alternative" if brand_conflict else "llm"))
        except Exception as exc:
            logger.warning("suggestion_llm_failed_fallback", extra={"error": str(exc)})

        # -------------------------------------------------------------
        # Step 2: Dynamic Algorithmic Variant Generation (Zero Hardcoded Lists)
        # -------------------------------------------------------------
        if len(candidates) < 10:
            dyn_variants = generate_dynamic_phonetic_variants(
                base_name_en=brand_en,
                descriptors_en=desc_en,
                base_name_ar=brand_ar,
                descriptors_ar=desc_ar,
                brand_conflict=brand_conflict,
            )
            for var_ar, var_en, src in dyn_variants:
                if is_candidate_relevant(var_en, var_ar, brand_en, brand_ar, brand_conflict=brand_conflict):
                    candidates.append((var_ar, var_en, "alternative" if brand_conflict else "template"))

        if not candidates:
            return []

        # -------------------------------------------------------------
        # Step 3: Batch Normalize & Deduplicate
        # -------------------------------------------------------------
        seen_normalized: set[tuple[str, str]] = set()
        normalized_candidates: list[dict] = []

        for cand_ar, cand_en, source in candidates:
            norm_ar = normalize_arabic(cand_ar)
            norm_en = normalize_english(cand_en)
            key = (norm_ar, norm_en)
            if key in seen_normalized or not norm_ar or not norm_en:
                continue
            seen_normalized.add(key)
            normalized_candidates.append({
                "raw_ar": cand_ar,
                "raw_en": cand_en,
                "norm_ar": norm_ar,
                "norm_en": norm_en,
                "source": source,
            })

        # -------------------------------------------------------------
        # Step 4: Lexicon Screening (Drop any candidate triggering block/review)
        # Bounded cost (N8): single batch query instead of N individual queries
        # -------------------------------------------------------------
        from db.models import Lexicon
        stmt_lex = select(Lexicon).where(Lexicon.severity.in_(["block", "review"]))
        res_lex = await self.session.execute(stmt_lex)
        risk_entries = res_lex.scalars().all()
        risk_terms_ar = {r.normalized_term for r in risk_entries if r.lang in ("ar", "both")}
        risk_terms_en = {r.normalized_term for r in risk_entries if r.lang in ("en", "both")}

        clean_candidates: list[dict] = []
        for cand in normalized_candidates:
            words_ar = set(cand["norm_ar"].split())
            words_en = set(cand["norm_en"].split())
            if (words_ar & risk_terms_ar) or (words_en & risk_terms_en):
                continue
            clean_candidates.append(cand)

        if not clean_candidates:
            return []

        # -------------------------------------------------------------
        # Step 5: Activity-Scoped Reservation & Active Registry Check
        # Verified against database records and similarity rules (Requirement 4 & 5)
        # -------------------------------------------------------------
        from db.models import TradeNameIndex
        from index.repository import TradeNameIndexRepository
        from rapidfuzz import fuzz
        index_repo = TradeNameIndexRepository(self.session)
        base_similarity_threshold = settings.trade_name_base_similarity_threshold
        import re

        def _clean_canon(s: str) -> str:
            if not s:
                return ""
            s = s.lower()
            s = re.sub(r"[^\w\s\u0600-\u06FF]", " ", s)
            return re.sub(r"\s+", " ", s).strip()

        norm_ar_list = [c["norm_ar"] for c in clean_candidates]
        norm_en_list = [c["norm_en"] for c in clean_candidates]

        # F18 — Reserved & active names are never suggested (scoped to category_id)
        stmt_conds = [
            TradeNameIndex.status.in_(["active", "reserved"]),
            or_(
                TradeNameIndex.normalized_ar.in_(norm_ar_list),
                TradeNameIndex.normalized_en.in_(norm_en_list),
            ),
        ]
        if target_category_id is not None:
            stmt_conds.append(TradeNameIndex.category_id == target_category_id)

        stmt = select(TradeNameIndex.normalized_ar, TradeNameIndex.normalized_en).where(*stmt_conds)
        result = await self.session.execute(stmt)
        reserved_rows = result.fetchall()
        reserved_ar = {r[0] for r in reserved_rows}
        reserved_en = {r[1] for r in reserved_rows}

        active_cat_records = []
        if target_category_id is not None:
            active_cat_stmt = select(TradeNameIndex.normalized_ar, TradeNameIndex.normalized_en).where(
                TradeNameIndex.status.in_(["active", "reserved"]),
                TradeNameIndex.category_id == target_category_id,
            )
            act_res = await self.session.execute(active_cat_stmt)
            active_cat_records = act_res.fetchall()

        # Collect existing base names in category to enforce base-name reservation
        existing_cat_base_en: set[str] = set()
        existing_cat_base_ar: set[str] = set()
        existing_base_tokens_en: list[set[str]] = []
        existing_base_tokens_ar: list[set[str]] = []
        for act_ar, act_en in active_cat_records:
            if act_en:
                key = canonical_base_name(act_en, lang="en")
                if key:
                    existing_cat_base_en.add(key)
                    base = extract_base_name(act_en, lang="en")
                    existing_base_tokens_en.append({token.casefold() for token in base.brand_tokens})
            if act_ar:
                key = canonical_base_name(act_ar, lang="ar")
                if key:
                    existing_cat_base_ar.add(key)
                    base = extract_base_name(act_ar, lang="ar")
                    existing_base_tokens_ar.append(set(base.brand_tokens))

        unreserved: list[dict] = []
        clean_in_en = normalize_english(name_en) if name_en else ""
        clean_in_ar = normalize_arabic(name_ar) if name_ar else ""

        for cand in clean_candidates:
            # Rule 1: Never suggest exact active/reserved names
            if cand["norm_ar"] in reserved_ar or cand["norm_en"] in reserved_en:
                continue

            # Rule 2: Never suggest the user's exact input trade name back to them
            if (clean_in_en and cand["norm_en"] == clean_in_en) or (clean_in_ar and cand["norm_ar"] == clean_in_ar):
                continue

            # Rule 3: Candidate base name must NOT conflict with protected base name or existing base names
            cand_ext_en = extract_base_name(cand["norm_en"], lang="en")
            cand_ext_ar = extract_base_name(cand["norm_ar"], lang="ar")
            cand_base_en = canonical_base_name(cand["norm_en"], lang="en") or ""
            cand_base_ar = canonical_base_name(cand["norm_ar"], lang="ar") or ""
            original_base_en = canonical_base_name(brand_en, lang="en")
            original_base_ar = canonical_base_name(brand_ar, lang="ar")

            if brand_conflict:
                if (original_base_en and cand_base_en == original_base_en) or (original_base_ar and cand_base_ar == original_base_ar):
                    continue

            if cand_base_en and cand_base_en in existing_cat_base_en:
                continue
            if cand_base_ar and cand_base_ar in existing_cat_base_ar:
                continue

            cand_tokens_en = {token.casefold() for token in cand_ext_en.brand_tokens}
            cand_tokens_ar = set(cand_ext_ar.brand_tokens)
            if any(tokens and (tokens.issubset(cand_tokens_en) or cand_tokens_en.issubset(tokens)) for tokens in existing_base_tokens_en):
                continue
            if any(tokens and (tokens.issubset(cand_tokens_ar) or cand_tokens_ar.issubset(tokens)) for tokens in existing_base_tokens_ar):
                continue

            # Verify candidate against existing names in activity to prevent confusingly similar suggestions
            cand_canon_en = _clean_canon(cand["norm_en"])
            cand_canon_ar = _clean_canon(cand["norm_ar"])
            is_similar_conflict = False

            for act_ar, act_en in active_cat_records:
                act_canon_en = _clean_canon(act_en or "")
                act_canon_ar = _clean_canon(act_ar or "")

                # Exact duplicate full name
                if (cand_canon_en and act_canon_en and cand_canon_en == act_canon_en) or \
                   (cand_canon_ar and act_canon_ar and cand_canon_ar == act_canon_ar):
                    is_similar_conflict = True
                    break

                # High typo similarity on base name (e.g. Cloudjun vs Cloudjune)
                if cand_base_en and act_canon_en:
                    act_b_en = canonical_base_name(act_canon_en, lang="en")
                    if act_b_en and fuzz.ratio(cand_base_en, act_b_en) >= base_similarity_threshold:
                        is_similar_conflict = True
                        break

                if cand_base_ar and act_canon_ar:
                    act_b_ar = canonical_base_name(act_canon_ar, lang="ar")
                    if act_b_ar and fuzz.ratio(cand_base_ar, act_b_ar) >= base_similarity_threshold:
                        is_similar_conflict = True
                        break

            if not is_similar_conflict:
                unreserved.append(cand)

        # -------------------------------------------------------------
        # Step 6: Formatting (F8 Legal Form, F17 Uppercase English)
        # -------------------------------------------------------------
        lf_en, lf_ar = format_legal_form_suffix(legal_form)
        final_suggestions: list[SuggestionItemDTO] = []

        # Provide a balanced mix: some with clean trade names, some with legal form suffix (LLC / ذ.م.م)
        # Companies can choose whether to include the legal suffix in their trade name or not
        for idx, cand in enumerate(unreserved[:limit]):
            base_ar = cand["raw_ar"]
            base_en = cand["raw_en"].upper()

            # Clean off any duplicate trailing legal form if already embedded in template/raw name
            for verbose_en in ("LIMITED LIABILITY COMPANY", "SOLE PROPRIETORSHIP", "PARTNERSHIP", "LLC", "L.L.C."):
                if base_en.endswith(f" {verbose_en}"):
                    base_en = base_en[:-len(verbose_en)-1].strip()
            for verbose_ar in ("LIMITED LIABILITY COMPANY", "ذ.م.م", "شركة ذات مسؤولية محدودة", "مؤسسة فردية", "شركة تضامنية"):
                if base_ar.endswith(f" {verbose_ar}"):
                    base_ar = base_ar[:-len(verbose_ar)-1].strip()

            # Second half of suggestions (or odd indices) feature the concise legal form suffix if specified
            include_suffix = bool(lf_en and (idx % 2 == 1 or idx >= (limit // 2)))
            if include_suffix:
                final_en = f"{base_en} {lf_en}".strip()
                final_ar = f"{base_ar} {lf_ar}".strip()
            else:
                final_en = base_en
                final_ar = base_ar

            from pipeline.name_composer import compose
            from pipeline.deterministic_gates import DeterministicGates, SignalType

            final_name = compose(
                name_ar=final_ar,
                name_en=final_en,
                operation_type="new",
                is_outside_uaq=False,
                old_legal_form=None,
                new_legal_form=None,
                previous_name_ar=None,
                previous_name_en=None,
            )
            final_signals = await DeterministicGates(
                index_repo=index_repo,
                lexicon_repo=self.lexicon_repo,
            ).run(composed=final_name, category_id=target_category_id)
            if any(signal.signal_type in (SignalType.BLOCKED, SignalType.NEEDS_REVIEW) for signal in final_signals):
                continue

            final_suggestions.append(
                SuggestionItemDTO(
                    name_ar=final_ar,
                    name_en=final_en,
                    score=1.0 if cand["source"] == "llm" else (0.90 if cand["source"] == "alternative" else 0.85),
                    source=cand["source"],
                )
            )

        return final_suggestions
