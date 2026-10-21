"""
backend/scripts/seed_db.py
Comprehensive database seeding script for Trade Name Intelligence Service.

Seeds:
  1. Active Trade Names (trade_name_index) with normalized keys and phonetic keys
     spanning multiple business categories (Restaurant, General Trading, Tech, Services, etc.)
  2. DED Compliance Lexicon (lexicon) for prohibited terms, divine names, special terms, etc.
  3. Default AI Analyzer System Prompt (prompt_version)
"""
import asyncio
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from db.models import Lexicon, PromptVersion, TradeNameIndex
from db.session import AsyncSessionLocal
from index.phonetic import generate_phonetic_key_pair
from llm.prompts import DEFAULT_ANALYZER_SYSTEM_PROMPT
from pipeline.normalizer import normalize_arabic, normalize_english

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_db")

# ---------------------------------------------------------------------------
# 1. Registered Trade Names to Seed
# ---------------------------------------------------------------------------
SAMPLE_TRADE_NAMES = [
    # --- Category 4: Food, Beverages & Restaurants (REST_004) ---
    {
        "trade_name_id": 1001,
        "name_ar": "مطعم صحراء",
        "name_en": "Sahra Restaurant",
        "category_id": 4,
        "status": "active",
    },
    {
        "trade_name_id": 1002,
        "name_ar": "مطعم الصحراء الذهبية",
        "name_en": "Golden Sahra Restaurant",
        "category_id": 4,
        "status": "active",
    },
    {
        "trade_name_id": 1003,
        "name_ar": "واحة الصحراء للمأكولات",
        "name_en": "Sahra Oasis Dine",
        "category_id": 4,
        "status": "active",
    },
    {
        "trade_name_id": 1004,
        "name_ar": "كافيه ومخبز النور",
        "name_en": "Al Noor Cafe & Bakery",
        "category_id": 4,
        "status": "active",
    },
    {
        "trade_name_id": 1005,
        "name_ar": "برغر ستيشن",
        "name_en": "Burger Station",
        "category_id": 4,
        "status": "active",
    },
    {
        "trade_name_id": 1006,
        "name_ar": "مقهى الفهد الشعبي",
        "name_en": "Al Fahad Traditional Cafe",
        "category_id": 4,
        "status": "active",
    },
    {
        "trade_name_id": 1007,
        "name_ar": "مطعم بيت البركة للحلويات",
        "name_en": "Beit Al Baraka Sweets & Restaurant",
        "category_id": 4,
        "status": "active",
    },
    {
        "trade_name_id": 1008,
        "name_ar": "مطعم زعفران وفستق",
        "name_en": "Zafaran & Fustuq Restaurant",
        "category_id": 4,
        "status": "active",
    },
    {
        "trade_name_id": 1009,
        "name_ar": "شاورما وفطاير الشام",
        "name_en": "Al Sham Shawarma & Pastries",
        "category_id": 4,
        "status": "active",
    },
    {
        "trade_name_id": 1010,
        "name_ar": "فلكانو كافيه ولاونج",
        "name_en": "Volcano Cafe & Lounge",
        "category_id": 4,
        "status": "active",
    },

    # --- Category 1: Commercial & General Trading (COMM_001) ---
    {
        "trade_name_id": 2001,
        "name_ar": "الأفق للتجارة العامة",
        "name_en": "Al Ofuq General Trading",
        "category_id": 1,
        "status": "active",
    },
    {
        "trade_name_id": 2002,
        "name_ar": "الصقر لتجارة المواد الغذائية",
        "name_en": "Al Saqr Foodstuff Trading",
        "category_id": 1,
        "status": "active",
    },
    {
        "trade_name_id": 2003,
        "name_ar": "الرواد للاستيراد والتصدير",
        "name_en": "Al Rowad Import & Export",
        "category_id": 1,
        "status": "active",
    },
    {
        "trade_name_id": 2004,
        "name_ar": "نجمة الخليج للتجارة",
        "name_en": "Gulf Star Trading",
        "category_id": 1,
        "status": "active",
    },
    {
        "trade_name_id": 2005,
        "name_ar": "البريق لتجارة الإلكترونيات",
        "name_en": "Al Bareeq Electronics Trading",
        "category_id": 1,
        "status": "active",
    },

    # --- Category 3: Information Technology & Software (TECH_003) ---
    {
        "trade_name_id": 3001,
        "name_ar": "كلاود تك للحلول البرمجية",
        "name_en": "Cloud Tech Software Solutions",
        "category_id": 3,
        "status": "active",
    },
    {
        "trade_name_id": 3002,
        "name_ar": "سايبر برو لأنظمة المعلومات",
        "name_en": "Cyber Pro Information Systems",
        "category_id": 3,
        "status": "active",
    },
    {
        "trade_name_id": 3003,
        "name_ar": "ذكاء للتقنيات الحديثة",
        "name_en": "Thakaa Modern Technologies",
        "category_id": 3,
        "status": "active",
    },
    {
        "trade_name_id": 3004,
        "name_ar": "بيكسل ديجيتال ميديا للتسويق",
        "name_en": "Pixel Digital Media Marketing",
        "category_id": 3,
        "status": "active",
    },

    # --- Category 2: Professional Services & Consultancy (SERV_002) ---
    {
        "trade_name_id": 4001,
        "name_ar": "الثقة للاستشارات الإدارية",
        "name_en": "Al Theqa Management Consulting",
        "category_id": 2,
        "status": "active",
    },
    {
        "trade_name_id": 4002,
        "name_ar": "رؤية للدراسات الاقتصادية",
        "name_en": "Roya Economic Studies",
        "category_id": 2,
        "status": "active",
    },
    {
        "trade_name_id": 4003,
        "name_ar": "الريادة لخدمات رجال الأعمال",
        "name_en": "Al Reyada Businessmen Services",
        "category_id": 2,
        "status": "active",
    },

    # --- Category 5: Real Estate & Property Management (REAL_005) ---
    {
        "trade_name_id": 5001,
        "name_ar": "ديار أم القيوين العقارية",
        "name_en": "Diyar Umm Al Quwain Real Estate",
        "category_id": 5,
        "status": "active",
    },
    {
        "trade_name_id": 5002,
        "name_ar": "المرسى للوساطة العقارية",
        "name_en": "Al Marsa Real Estate Brokerage",
        "category_id": 5,
        "status": "active",
    },

    # --- Category 6: Construction & Contracting (CONT_006) ---
    {
        "trade_name_id": 6001,
        "name_ar": "البناء الحديث للمقاولات العامة",
        "name_en": "Al Benaa Al Hadeeth General Contracting",
        "category_id": 6,
        "status": "active",
    },
    {
        "trade_name_id": 6002,
        "name_ar": "أساسات الخليج للأعمال الإنشائية",
        "name_en": "Gulf Foundations Construction Works",
        "category_id": 6,
        "status": "active",
    },
]

# ---------------------------------------------------------------------------
# 2. Compliance Lexicon Terms to Seed
# ---------------------------------------------------------------------------
SAMPLE_LEXICON_TERMS = [
    # Divine Names (Block)
    {"term": "الله", "category": "divine_name", "lang": "ar", "severity": "block", "variants": ["الله", "الإله"]},
    {"term": "allah", "category": "divine_name", "lang": "en", "severity": "block", "variants": ["allah", "alla"]},
    {"term": "الرحمن", "category": "divine_name", "lang": "ar", "severity": "block", "variants": ["الرحمن"]},
    {"term": "al rahman", "category": "divine_name", "lang": "en", "severity": "block", "variants": ["al rahman", "alrahman"]},
    {"term": "القدوس", "category": "divine_name", "lang": "ar", "severity": "block", "variants": ["القدوس"]},

    # Special / Reserved Governmental Terms (Block or Review)
    {"term": "royal", "category": "special", "lang": "en", "severity": "block", "variants": ["royal", "royale"]},
    {"term": "ملكي", "category": "special", "lang": "ar", "severity": "block", "variants": ["ملكي", "ملكية"]},
    {"term": "أميري", "category": "special", "lang": "ar", "severity": "block", "variants": ["اميري", "أميري"]},
    {"term": "emiri", "category": "special", "lang": "en", "severity": "block", "variants": ["emiri", "amiri"]},
    {"term": "police", "category": "special", "lang": "en", "severity": "block", "variants": ["police"]},
    {"term": "شرطة", "category": "special", "lang": "ar", "severity": "block", "variants": ["شرطة"]},
    {"term": "وزارة", "category": "special", "lang": "ar", "severity": "block", "variants": ["وزارة", "وزاريه"]},
    {"term": "ministry", "category": "special", "lang": "en", "severity": "block", "variants": ["ministry"]},
    {"term": "حكومة", "category": "special", "lang": "ar", "severity": "block", "variants": ["حكومة", "حكومي"]},
    {"term": "government", "category": "special", "lang": "en", "severity": "block", "variants": ["government", "govt"]},

    # Prohibited Activity / Illegal (Block)
    {"term": "casino", "category": "prohibited", "lang": "en", "severity": "block", "variants": ["casino", "kasino"]},
    {"term": "كازينو", "category": "prohibited", "lang": "ar", "severity": "block", "variants": ["كازينو"]},
    {"term": "gambling", "category": "prohibited", "lang": "en", "severity": "block", "variants": ["gambling", "gamble"]},
    {"term": "قمار", "category": "prohibited", "lang": "ar", "severity": "block", "variants": ["قمار", "ميسر"]},
    {"term": "lottery", "category": "prohibited", "lang": "en", "severity": "block", "variants": ["lottery", "lotto"]},
    {"term": "يانصيب", "category": "prohibited", "lang": "ar", "severity": "block", "variants": ["يانصيب"]},
    {"term": "wine", "category": "prohibited", "lang": "en", "severity": "block", "variants": ["wine", "winery"]},
    {"term": "خمور", "category": "prohibited", "lang": "ar", "severity": "block", "variants": ["خمور", "نبيذ"]},

    # Sensitive Family / Ruling Dynasty (Review/Block)
    {"term": "المعلا", "category": "family_name", "lang": "ar", "severity": "block", "variants": ["المعلا", "آل معلا"]},
    {"term": "al mualla", "category": "family_name", "lang": "en", "severity": "block", "variants": ["al mualla", "almualla"]},

    # Geographic Location (Review)
    {"term": "أم القيوين", "category": "location", "lang": "ar", "severity": "review", "variants": ["أم القيوين", "ام القيوين"]},
    {"term": "umm al quwain", "category": "location", "lang": "en", "severity": "review", "variants": ["umm al quwain", "uaq"]},
    {"term": "الإمارات", "category": "location", "lang": "ar", "severity": "review", "variants": ["الإمارات", "الامارات"]},
    {"term": "emirates", "category": "location", "lang": "en", "severity": "review", "variants": ["emirates", "uae"]},
]


async def seed_data():
    logger.info("Starting database seeding...")
    expiry = date.today() + timedelta(days=365)

    async with AsyncSessionLocal() as session:
        # 1. Seed Active Prompt
        stmt_prompt = select(PromptVersion).where(PromptVersion.name == "analyzer_v1", PromptVersion.active.is_(True))
        res_prompt = await session.execute(stmt_prompt)
        if not res_prompt.scalar_one_or_none():
            prompt = PromptVersion(
                name="analyzer_v1",
                text=DEFAULT_ANALYZER_SYSTEM_PROMPT,
                active=True,
            )
            session.add(prompt)
            logger.info("Seeded active prompt analyzer_v1")

        # 2. Seed Trade Name Index
        from pipeline.base_name_extractor import canonical_base_name

        inserted_names = 0
        for item in SAMPLE_TRADE_NAMES:
            stmt_check = select(TradeNameIndex).where(TradeNameIndex.trade_name_id == item["trade_name_id"])
            res = await session.execute(stmt_check)
            existing = res.scalar_one_or_none()

            norm_ar = normalize_arabic(item["name_ar"])
            norm_en = normalize_english(item["name_en"])
            phonetic_key = generate_phonetic_key_pair(norm_ar, norm_en)

            if not existing:
                idx_entry = TradeNameIndex(
                    trade_name_id=item["trade_name_id"],
                    normalized_ar=norm_ar,
                    normalized_en=norm_en,
                    phonetic_key=phonetic_key,
                    category_id=item["category_id"],
                    base_name_en=canonical_base_name(norm_en, lang="en"),
                    base_name_ar=canonical_base_name(norm_ar, lang="ar"),
                    status=item["status"],
                    expiry_date=expiry,
                )
                session.add(idx_entry)
                inserted_names += 1
            else:
                # Update normalized forms and phonetic key to ensure consistency
                existing.normalized_ar = norm_ar
                existing.normalized_en = norm_en
                existing.phonetic_key = phonetic_key
                existing.category_id = item["category_id"]
                existing.base_name_en = canonical_base_name(norm_en, lang="en")
                existing.base_name_ar = canonical_base_name(norm_ar, lang="ar")
                existing.status = item["status"]

        logger.info("Seeded %d new trade names into trade_name_index (total: %d)", inserted_names, len(SAMPLE_TRADE_NAMES))

        # 3. Seed Lexicon
        inserted_lex = 0
        for item in SAMPLE_LEXICON_TERMS:
            norm_term = normalize_arabic(item["term"]) if item["lang"] == "ar" else normalize_english(item["term"])
            stmt_lex = select(Lexicon).where(
                Lexicon.normalized_term == norm_term,
                Lexicon.category == item["category"],
                Lexicon.lang == item["lang"],
            )
            res_lex = await session.execute(stmt_lex)
            if not res_lex.scalar_one_or_none():
                lex = Lexicon(
                    term=item["term"],
                    normalized_term=norm_term,
                    category=item["category"],
                    lang=item["lang"],
                    severity=item["severity"],
                    variants=item.get("variants", []),
                    approved_by="DED-SYSTEM",
                )
                session.add(lex)
                inserted_lex += 1

        logger.info("Seeded %d new compliance terms into lexicon (total: %d)", inserted_lex, len(SAMPLE_LEXICON_TERMS))

        await session.commit()
        logger.info("Database seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_data())
