"""
pipeline/base_name_extractor.py
Dynamic, non-hardcoded identification of distinctive base names and descriptive terms.

Fulfills Requirements:
1. Dynamic Base-Name Identification: Separates distinctive brand tokens from generic
   business descriptors and legal entity terms.
2. Word-order invariance: Identifies the distinctive base name regardless of whether
   descriptors appear as prefixes, suffixes, or infixes (e.g. 'Technologies Cloudjune'
   and 'Cloudjune Technologies' both yield 'Cloudjune').
3. Multi-language support: Handles English and Arabic linguistic structures.
4. Confidence & Ambiguity detection: Flags generic names (e.g. 'General Trading LLC')
   with confidence=0.0 and is_generic=True so they are not silently approved.
5. Dynamic catalogue integration: Uses official UAE / DED business activity terms
   from pipeline/activity_catalogue.py to determine industry descriptors dynamically.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from pipeline.activity_catalogue import OFFICIAL_ACTIVITY_CATALOGUE


# ---------------------------------------------------------------------------
# Dynamic Descriptor Registry
# Built from official activity catalogue + standard commercial entity terms
# ---------------------------------------------------------------------------

def _build_catalogue_descriptor_phrases() -> tuple[set[tuple[str, ...]], set[tuple[str, ...]]]:
    phrases_en: set[tuple[str, ...]] = set()
    phrases_ar: set[tuple[str, ...]] = set()
    for category in OFFICIAL_ACTIVITY_CATALOGUE:
        en_terms = [category.get("name_en", "")]
        ar_terms = [category.get("name_ar", "")]
        en_terms.extend(category.get("representative_activities", []))
        for isic in category.get("isic_codes", []):
            en_terms.append(isic.get("name_en", ""))
            ar_terms.append(isic.get("name_ar", ""))
        for phrase in en_terms:
            tokens = tuple(re.findall(r"\w+", phrase.lower()))
            if len(tokens) > 1:
                phrases_en.add(tokens)
        for phrase in ar_terms:
            tokens = tuple(re.findall(r"[\u0600-\u06FF]+", phrase))
            if len(tokens) > 1:
                phrases_ar.add(tokens)
    return phrases_en, phrases_ar


_CATALOGUE_PHRASES_EN, _CATALOGUE_PHRASES_AR = _build_catalogue_descriptor_phrases()


def _configured_terms(language: str) -> set[str]:
    from config.settings import get_settings

    setting = (
        get_settings().trade_name_descriptors_en
        if language == "en"
        else get_settings().trade_name_descriptors_ar
    )
    return {term.strip().casefold() for term in setting.split(",") if term.strip()}

# Standard corporate structure and legal entity tokens (EN)
LEGAL_FORMS_EN: set[str] = {
    "llc", "l.l.c", "pjsc", "pr.jsc", "psc", "fze", "fzco", "ltd", "limited",
    "inc", "corp", "corporation", "co", "company", "sole", "proprietorship",
    "establishment", "est", "branch", "partnership", "plc", "private", "pvt"
}

# Standard generic commercial descriptors (EN)
COMMERCIAL_TERMS_EN: set[str] = {
    "it", "ict", "ai", "hr", "pr", "iot", "b2b", "b2c",
    "trading", "services", "service", "solutions", "solution", "consultancy",
    "consulting", "technologies", "technology", "tech",
    "systems", "system", "software", "digital", "innovations", "innovation",
    "labs", "lab", "logistics", "management", "commercial", "industries", "industry",
    "industrial", "general", "center", "centre",
    "store", "stores", "shop", "shops", "market", "mart", "retail", "wholesale",
    "operations", "consultants", "advisory", "foodstuff", "fashion", "fashions", "clothing",
    "restaurant", "restaurants", "cafe", "café", "dining", "kitchen", "bistro"
}

# Grammatical particles / stop words (EN)
STOPWORDS_EN: set[str] = {"and", "&", "the", "of", "for", "in", "by", "with", "a", "an"}

ALL_DESCRIPTORS_EN: set[str] = LEGAL_FORMS_EN | COMMERCIAL_TERMS_EN

# Standard corporate structure and legal entity tokens (AR)
LEGAL_FORMS_AR: set[str] = {
    "ذ.م.م", "ش.م.م", "ش.م.ع", "ش.م.خ", "مؤسسة", "شركة", "فرع", "القابضة", "قابضة",
    "مجموعة", "شراكة", "تضامنية", "مساهمة", "فردية", "مؤسسة فردية", "ذات مسؤولية محدودة"
}

# Standard generic commercial descriptors (AR)
COMMERCIAL_TERMS_AR: set[str] = {
    "للتجارة", "تجارة", "للخدمات", "خدمات", "خدمة", "للحلول", "حلول", "للاستشارات",
    "استشارات", "استشاري", "للتكنولوجيا", "تكنولوجيا", "للتقنية", "تقنية", "تقنيات",
    "للتقنيات", "للأنظمة", "أنظمة", "نظام", "للبرمجيات", "برمجيات", "برامج", "رقمية",
    "الرقمية", "للرقمية", "العامة", "عامة", "الدولية", "دولية", "العالمية", "عالمية",
    "للمشاريع", "مشاريع", "مشروع", "لإدارة", "إدارة", "لوجستية", "اللوجستية",
    "صناعية", "الصناعية", "للصناعة", "صناعة", "ابتكار", "للابتكار", "الذكية", "ذكية",
    "اكسبريس", "سريع", "مركز", "المركز", "وكالة", "الوكالة", "متجر", "سوق",
    "مطعم", "مطاعم", "كافيه", "مقهى", "مأكولات", "وجبات", "لاونج", "بسترو",
    "معلومات", "المعلومات",
}

# Grammatical particles / stop words (AR)
STOPWORDS_AR: set[str] = {"و", "في", "من", "عن", "على", "إلى", "لـ", "مع", "ال"}

ALL_DESCRIPTORS_AR: set[str] = LEGAL_FORMS_AR | COMMERCIAL_TERMS_AR


@dataclass
class ExtractedBaseName:
    """Structured result of dynamic base-name and descriptor isolation."""
    raw_name: str
    normalized_name: str
    base_name: str
    descriptors: str
    legal_form: Optional[str]
    lang: str
    is_generic: bool
    confidence: float
    brand_tokens: list[str] = field(default_factory=list)
    descriptor_tokens: list[str] = field(default_factory=list)


class DynamicBaseNameExtractor:
    """
    Extracts the distinctive base name from arbitrary trade names dynamically.
    Works independently of word order, legal form positioning, and casing.
    """

    @classmethod
    def extract(cls, name: str, lang: Optional[str] = None) -> ExtractedBaseName:
        """
        Extracts distinctive base name and descriptors from raw trade name.
        """
        if not name or not name.strip():
            return ExtractedBaseName(
                raw_name="",
                normalized_name="",
                base_name="",
                descriptors="",
                legal_form=None,
                lang="en" if lang != "ar" else "ar",
                is_generic=True,
                confidence=0.0,
            )

        raw = name.strip()
        # Auto-detect language if not explicitly provided
        is_ar = bool(re.search(r"[\u0600-\u06FF]", raw)) if lang is None else (lang == "ar")
        detected_lang = "ar" if is_ar else "en"

        if is_ar:
            return cls._extract_ar(raw)
        else:
            return cls._extract_en(raw)

    @classmethod
    def _extract_en(cls, raw: str) -> ExtractedBaseName:
        # Clean punctuation while keeping hyphens and words
        clean = re.sub(r"[^\w\s]", " ", raw)
        clean = re.sub(r"\s+", " ", clean).strip()
        tokens = clean.split()
        configured_descriptors = _configured_terms("en")
        catalogue_descriptor_tokens: set[int] = set()
        token_values = [token.casefold() for token in tokens]
        for phrase in _CATALOGUE_PHRASES_EN:
            width = len(phrase)
            for start in range(len(tokens) - width + 1):
                if (start == 0 or start + width == len(tokens)) and tuple(token_values[start:start + width]) == phrase:
                    catalogue_descriptor_tokens.update(range(start, start + width))

        brand_tokens: list[str] = []
        desc_tokens: list[str] = []
        found_legal_form: Optional[str] = None

        for index, tok in enumerate(tokens):
            tok_low = tok.lower()

            if tok_low in STOPWORDS_EN:
                continue

            if tok_low in LEGAL_FORMS_EN:
                found_legal_form = tok.upper()
                desc_tokens.append(tok)
                continue

            if tok_low in ALL_DESCRIPTORS_EN or tok_low in configured_descriptors or index in catalogue_descriptor_tokens:
                desc_tokens.append(tok)
            else:
                brand_tokens.append(tok)

        base_name = " ".join(brand_tokens).strip()
        descriptors = " ".join(desc_tokens).strip()

        # If brand_tokens is empty, the entire name is composed of generic descriptors!
        if not brand_tokens:
            return ExtractedBaseName(
                raw_name=raw,
                normalized_name=clean,
                base_name="",
                descriptors=descriptors,
                legal_form=found_legal_form,
                lang="en",
                is_generic=True,
                confidence=0.0,
                brand_tokens=[],
                descriptor_tokens=desc_tokens,
            )

        # Confidence heuristic:
        # High confidence if 1-3 distinct brand tokens are isolated
        # Moderate confidence if more than 3 brand tokens
        conf = 1.0 if len(brand_tokens) in (1, 2) else (0.85 if len(brand_tokens) == 3 else 0.60)

        return ExtractedBaseName(
            raw_name=raw,
            normalized_name=clean,
            base_name=base_name,
            descriptors=descriptors,
            legal_form=found_legal_form,
            lang="en",
            is_generic=False,
            confidence=conf,
            brand_tokens=brand_tokens,
            descriptor_tokens=desc_tokens,
        )

    @classmethod
    def _extract_ar(cls, raw: str) -> ExtractedBaseName:
        # Pre-extract Arabic legal forms like ذ.م.م, ش.م.ع, ش.م.م
        found_legal_form: Optional[str] = None
        cleaned_raw = raw
        ar_legal_patterns = [
            (r"\bذ\s*[\.\-]?\s*م\s*[\.\-]?\s*م\b", "ذ.م.م"),
            (r"\bش\s*[\.\-]?\s*م\s*[\.\-]?\s*ع\b", "ش.م.ع"),
            (r"\bش\s*[\.\-]?\s*م\s*[\.\-]?\s*خ\b", "ش.م.خ"),
            (r"\bش\s*[\.\-]?\s*م\s*[\.\-]?\s*م\b", "ش.م.م"),
            (r"\bش\s*[\.\-]?\s*ذ\s*[\.\-]?\s*م\s*[\.\-]?\s*م\b", "ش.ذ.م.م"),
        ]
        for pat, repr_form in ar_legal_patterns:
            if re.search(pat, cleaned_raw):
                found_legal_form = repr_form
                cleaned_raw = re.sub(pat, " ", cleaned_raw)

        # Normalize Arabic diacritics and punctuation
        clean = re.sub(r"[^\u0600-\u06FF\w\s]", " ", cleaned_raw)
        clean = re.sub(r"\s+", " ", clean).strip()
        tokens = clean.split()
        configured_descriptors = _configured_terms("ar")
        catalogue_descriptor_tokens: set[int] = set()
        token_values = [token.casefold() for token in tokens]
        for phrase in _CATALOGUE_PHRASES_AR:
            width = len(phrase)
            for start in range(len(tokens) - width + 1):
                if (start == 0 or start + width == len(tokens)) and tuple(token_values[start:start + width]) == phrase:
                    catalogue_descriptor_tokens.update(range(start, start + width))

        brand_tokens: list[str] = []
        desc_tokens: list[str] = []
        if found_legal_form:
            desc_tokens.append(found_legal_form)

        for index, tok in enumerate(tokens):
            norm_tok = tok
            if norm_tok in STOPWORDS_AR or norm_tok in ("ذ", "م", "ع", "خ", "ش"):
                continue

            if norm_tok in LEGAL_FORMS_AR:
                if not found_legal_form:
                    found_legal_form = tok
                desc_tokens.append(tok)
                continue

            # Strip leading 'للـ' / 'لـ' / 'الـ' for matching against descriptor set
            stem_tok = re.sub(r"^(لل|ل|ال)", "", norm_tok)

            if (
                norm_tok in ALL_DESCRIPTORS_AR
                or stem_tok in ALL_DESCRIPTORS_AR
                or norm_tok.casefold() in configured_descriptors
                or stem_tok.casefold() in configured_descriptors
                or index in catalogue_descriptor_tokens
            ):
                desc_tokens.append(tok)
            else:
                brand_tokens.append(tok)

        base_name = " ".join(brand_tokens).strip()
        descriptors = " ".join(desc_tokens).strip()

        if not brand_tokens:
            return ExtractedBaseName(
                raw_name=raw,
                normalized_name=clean,
                base_name="",
                descriptors=descriptors,
                legal_form=found_legal_form,
                lang="ar",
                is_generic=True,
                confidence=0.0,
                brand_tokens=[],
                descriptor_tokens=desc_tokens,
            )

        conf = 1.0 if len(brand_tokens) in (1, 2) else (0.85 if len(brand_tokens) == 3 else 0.60)

        return ExtractedBaseName(
            raw_name=raw,
            normalized_name=clean,
            base_name=base_name,
            descriptors=descriptors,
            legal_form=found_legal_form,
            lang="ar",
            is_generic=False,
            confidence=conf,
            brand_tokens=brand_tokens,
            descriptor_tokens=desc_tokens,
        )


def extract_base_name(name: str, lang: Optional[str] = None) -> ExtractedBaseName:
    """Convenience helper to extract base name dynamically."""
    return DynamicBaseNameExtractor.extract(name, lang=lang)


def canonical_base_name(name: str, lang: Optional[str] = None) -> Optional[str]:
    """Return punctuation-, whitespace-, and case-insensitive base-name key."""
    extracted = extract_base_name(name, lang=lang)
    if extracted.is_generic:
        return None
    value = unicodedata.normalize("NFKC", extracted.base_name).casefold()
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    canonical = re.sub(r"[^\w]", "", value, flags=re.UNICODE)
    return canonical or None
