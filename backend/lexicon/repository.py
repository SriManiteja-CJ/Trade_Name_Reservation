"""
lexicon/repository.py
Async repository for the Lexicon table.

Responsibilities (Phase 1.4):
  - CRUD for Lexicon entries using SQLAlchemy 2.0 async
  - find_matches: exact normalized term lookup + RapidFuzz edit-distance check
    against the variants JSON array
  - list_all_by_category: for admin listing and bulk gate checks
  - upsert: for admin and Stage ⑨ proposal approval

Spec references:
  F4  — word checks: prohibited, profanity, unfriendly, special words,
         divine names, location names, family names
  E7  — LLM-proposed lexicon variants; human approves each before it enters
  §5.1 — Lexicon table schema
"""
from typing import Optional

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from db.models import Lexicon

settings = get_settings()


class LexiconEntry:
    """Lightweight DTO for a lexicon row."""
    __slots__ = (
        "id", "term", "normalized_term", "category",
        "lang", "severity", "variants", "approved_by",
    )

    def __init__(
        self,
        id: Optional[int],
        term: str,
        normalized_term: str,
        category: str,
        lang: str,
        severity: str,
        variants: Optional[list[str]] = None,
        approved_by: Optional[str] = None,
    ) -> None:
        self.id = id
        self.term = term
        self.normalized_term = normalized_term
        self.category = category
        self.lang = lang
        self.severity = severity
        self.variants = variants or []
        self.approved_by = approved_by

    @classmethod
    def from_orm(cls, row: Lexicon) -> "LexiconEntry":
        return cls(
            id=row.id,
            term=row.term,
            normalized_term=row.normalized_term,
            category=row.category,
            lang=row.lang,
            severity=row.severity,
            variants=row.variants or [],
            approved_by=row.approved_by,
        )


class LexiconRepository:
    """
    Async repository for lexicon operations.
    All methods require an injected AsyncSession.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_matches(
        self,
        normalized_term: str,
        lang: str,
    ) -> list[LexiconEntry]:
        """
        Find lexicon entries that match the given normalized term.

        Matching strategy (spec §3 Component ②: "lexicon match with variants
        and edit distance"):
          1. Exact match on normalized_term column (primary lookup)
          2. Fuzzy match of normalized_term against each entry's variants JSON
             array using RapidFuzz ratio >= settings.lexicon_fuzzy_threshold

        Args:
            normalized_term: Pre-normalized term from the Normalizer (Stage ①)
            lang: "ar" | "en" | "both" — filter to relevant entries

        Returns:
            List of matching LexiconEntry objects (may be empty).
        """
        # Query entries with matching lang scope
        lang_filter = Lexicon.lang.in_([lang, "both"])
        stmt = select(Lexicon).where(lang_filter)
        result = await self._session.execute(stmt)
        all_entries = result.scalars().all()

        matched: list[LexiconEntry] = []
        threshold = settings.lexicon_fuzzy_threshold

        words = normalized_term.split()

        for row in all_entries:
            entry = LexiconEntry.from_orm(row)

            # 1. Exact match on normalized_term or substring/word match in name
            norm_lex = row.normalized_term.strip()
            if (
                norm_lex == normalized_term
                or norm_lex in words
                or f" {norm_lex} " in f" {normalized_term} "
            ):
                matched.append(entry)
                continue

            # 2. Fuzzy match against words or whole name using RapidFuzz
            found = False
            targets = [norm_lex] + [str(v).strip() for v in (row.variants or [])]
            for target in targets:
                if fuzz.ratio(normalized_term, target) >= threshold:
                    matched.append(entry)
                    found = True
                    break
                for w in words:
                    if fuzz.ratio(w, target) >= threshold:
                        matched.append(entry)
                        found = True
                        break
                if found:
                    break

        return matched

    async def find_exact(self, normalized_term: str) -> list[LexiconEntry]:
        """Exact normalized_term lookup regardless of lang."""
        stmt = select(Lexicon).where(Lexicon.normalized_term == normalized_term)
        result = await self._session.execute(stmt)
        return [LexiconEntry.from_orm(r) for r in result.scalars().all()]

    async def list_all_by_category(self, category: str) -> list[LexiconEntry]:
        """
        Return all lexicon entries for a given F4 category.
        Used for bulk checks and admin listing.
        """
        stmt = select(Lexicon).where(Lexicon.category == category)
        result = await self._session.execute(stmt)
        return [LexiconEntry.from_orm(r) for r in result.scalars().all()]

    async def list_pending_proposals(self) -> list[LexiconEntry]:
        """
        Return entries where approved_by IS NULL (pending admin approval).
        Used by Admin/Lexicon/Proposals GET.
        """
        stmt = select(Lexicon).where(Lexicon.approved_by.is_(None))
        result = await self._session.execute(stmt)
        return [LexiconEntry.from_orm(r) for r in result.scalars().all()]

    async def upsert(self, entry: LexiconEntry) -> LexiconEntry:
        """
        Insert or update a lexicon entry.
        On conflict (same term + category + lang), update variants and approved_by.
        Used by admin CRUD and Stage ⑨ proposal approval (E7).

        Each proposed variant requires explicit human approval before entering
        the lexicon (E7: "approved by a human").
        approved_by must be non-null for the entry to be used in gate checks.
        """
        stmt = select(Lexicon).where(
            Lexicon.normalized_term == entry.normalized_term,
            Lexicon.category == entry.category,
            Lexicon.lang == entry.lang,
        )
        res = await self._session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.term = entry.term
            existing.severity = entry.severity
            existing.variants = entry.variants
            existing.approved_by = entry.approved_by
            await self._session.flush()
            return LexiconEntry.from_orm(existing)
        else:
            new_row = Lexicon(
                term=entry.term,
                normalized_term=entry.normalized_term,
                category=entry.category,
                lang=entry.lang,
                severity=entry.severity,
                variants=entry.variants,
                approved_by=entry.approved_by,
            )
            self._session.add(new_row)
            await self._session.flush()
            return LexiconEntry.from_orm(new_row)

    async def delete(self, entry_id: int) -> None:
        """Delete a lexicon entry by ID (used for rejected proposals)."""
        from sqlalchemy import delete as sa_delete
        stmt = sa_delete(Lexicon).where(Lexicon.id == entry_id)
        await self._session.execute(stmt)
