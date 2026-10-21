"""
index/repository.py
TradeNameIndex async repository.

Provides all query operations needed by:
  Stage ② — lookup_exact (F2 exact duplicate check)
  Stage ③ — lookup_phonetic, lookup_trigram, lookup_vector (F3 similarity search)
  Stage ⑦ — upsert, delete (F15 index sync)
  GET Search endpoint — lookup_trigram + lookup_vector (F19, E8)

All queries filter to status='active' by default (F2, F3, F21).
F21: Released/rejected names are excluded because they have status != 'active'.
     The sync worker sets status appropriately when a name is released/deleted.

Spec references:
  F2  — exact duplicate against active names, ignoring case/spaces, excl. current
  F3  — similarity check against existing names
  F15 — index stays in sync on insert, edit, release, delete
  F19 — keyword search over trade names
  F21 — rejected or released names become available (filtered out by status)
  E2  — phonetic + embedding matching
  E8  — fuzzy, cross-language search
  §5.1 — TradeNameIndex table

NOTE on embeddings: SQLAlchemy does not natively support pgvector's VECTOR type.
Vector operations use sqlalchemy text() with explicit SQL. The column is stored
as TEXT in the ORM model and cast with ::vector in queries (see Alembic migration
for the actual VECTOR(N) column definition).
"""
import re
from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TradeNameIndex

ACTIVE_STATUS = "active"


def canonical_clean(s: str) -> str:
    """Normalize casing, strip all punctuation and symbols, and collapse whitespace."""
    if not s:
        return ""
    s = s.lower()
    # remove punctuation and symbols (retain letters and digits)
    s = re.sub(r"[^\w\s\u0600-\u06FF]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class IndexEntry:
    """Lightweight DTO for a TradeNameIndex row."""
    id: int
    trade_name_id: int
    normalized_ar: str
    normalized_en: str
    phonetic_key: str
    category_id: Optional[int]
    status: str
    similarity_score: float = 0.0  # populated by similarity queries


class TradeNameIndexRepository:
    """
    Async repository for TradeNameIndex operations.
    Injected with an AsyncSession per request.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
      # -----------------------------------------------------------------------
    # Stage ② — Exact duplicate check (F2) with Activity Type Scoping
    # -----------------------------------------------------------------------
    async def lookup_exact(
        self,
        normalized_ar: str,
        normalized_en: str,
        category_id: Optional[int] = None,
        exclude_trade_name_id: Optional[int] = None,
    ) -> list[IndexEntry]:
        """
        Check for exact duplicates against ACTIVE names within category_id (if provided).
        Spec F2 & Activity Scope: Exact-duplicate check against active names,
        ignoring case, extra spaces, and punctuation, excluding the record being edited,
        scoped to the selected activity type.
        """
        norm_ar_clean = normalized_ar.strip() if normalized_ar else ""
        norm_en_clean = normalized_en.strip().lower() if normalized_en else ""

        canon_ar = canonical_clean(norm_ar_clean)
        canon_en = canonical_clean(norm_en_clean)

        conditions = []
        params = {}

        if norm_ar_clean:
            conditions.append("TRIM(normalized_ar) = :norm_ar")
            params["norm_ar"] = norm_ar_clean
        if norm_en_clean:
            conditions.append("LOWER(TRIM(normalized_en)) = :norm_en")
            params["norm_en"] = norm_en_clean

        category_clause = ""
        if category_id is not None:
            category_clause = "AND category_id = :category_id"
            params["category_id"] = category_id

        exclude_clause = "AND trade_name_id != :exclude_id" if exclude_trade_name_id is not None else ""
        if exclude_trade_name_id is not None:
            params["exclude_id"] = exclude_trade_name_id

        matched_entries: list[IndexEntry] = []
        seen_ids: set[int] = set()

        if conditions:
            match_clause = " OR ".join(conditions)
            sql = f"""
                SELECT id, trade_name_id, normalized_ar, normalized_en, phonetic_key,
                       category_id, status
                FROM trade_name_index
                WHERE status IN ('active', 'reserved')
                  {category_clause}
                  AND ({match_clause})
                  {exclude_clause}
            """
            result = await self._session.execute(text(sql), params)
            rows = result.fetchall()
            for r in rows:
                if r[1] not in seen_ids:
                    seen_ids.add(r[1])
                    matched_entries.append(
                        IndexEntry(
                            id=r[0],
                            trade_name_id=r[1],
                            normalized_ar=r[2],
                            normalized_en=r[3],
                            phonetic_key=r[4],
                            category_id=r[5],
                            status=r[6],
                        )
                    )

        # Also check canonical form equality (ignoring casing, punctuation, extra spaces)
        if canon_en or canon_ar:
            sql_canon = f"""
                SELECT id, trade_name_id, normalized_ar, normalized_en, phonetic_key,
                       category_id, status
                FROM trade_name_index
                WHERE status IN ('active', 'reserved')
                  {category_clause}
                  {exclude_clause}
            """
            canon_params = {}
            if category_id is not None:
                canon_params["category_id"] = category_id
            if exclude_trade_name_id is not None:
                canon_params["exclude_id"] = exclude_trade_name_id

            res_canon = await self._session.execute(text(sql_canon), canon_params)
            for r in res_canon.fetchall():
                if r[1] in seen_ids:
                    continue
                cand_canon_ar = canonical_clean(r[2] or "")
                cand_canon_en = canonical_clean(r[3] or "")
                is_canon_match = False
                if canon_en and cand_canon_en and canon_en == cand_canon_en:
                    is_canon_match = True
                elif canon_ar and cand_canon_ar and canon_ar == cand_canon_ar:
                    is_canon_match = True

                if is_canon_match:
                    seen_ids.add(r[1])
                    matched_entries.append(
                        IndexEntry(
                            id=r[0],
                            trade_name_id=r[1],
                            normalized_ar=r[2],
                            normalized_en=r[3],
                            phonetic_key=r[4],
                            category_id=r[5],
                            status=r[6],
                        )
                    )

        return matched_entries

    async def lookup_base_name_in_category(
        self,
        base_name_en: str,
        base_name_ar: str,
        category_id: Optional[int] = None,
        exclude_trade_name_id: Optional[int] = None,
    ) -> list[IndexEntry]:
        """
        Check if the distinctive base name is already registered/reserved under the selected activity (category_id).
        A category_id is required; base-name reservations are never global.
        Extracts base name from active entries dynamically using DynamicBaseNameExtractor.
        Also checks token-level and boundary matches:
          - Exact match against existing base name
          - Whole-token match within normalized_en / normalized_ar
        Prevents false positive substring blocking while strictly prohibiting reuse of the base name.
        """
        from pipeline.base_name_extractor import extract_base_name

        b_en = (base_name_en or "").strip().lower()
        b_ar = (base_name_ar or "").strip()
        if category_id is None:
            raise ValueError("category_id is required for activity-scoped base-name lookup")
        if not b_en and not b_ar:
            return []

        exclude_clause = "AND trade_name_id != :exclude_id" if exclude_trade_name_id is not None else ""
        sql = f"""
            SELECT id, trade_name_id, normalized_ar, normalized_en, phonetic_key,
                   category_id, status
            FROM trade_name_index
            WHERE status IN ('active', 'reserved')
              AND category_id = :category_id
              {exclude_clause}
        """
        params = {"category_id": category_id}
        if exclude_trade_name_id is not None:
            params["exclude_id"] = exclude_trade_name_id

        result = await self._session.execute(text(sql), params)
        rows = result.fetchall()

        matched: list[IndexEntry] = []
        b_en_words = set(b_en.split()) if b_en else set()

        for r in rows:
            entry = IndexEntry(
                id=r[0],
                trade_name_id=r[1],
                normalized_ar=r[2],
                normalized_en=r[3],
                phonetic_key=r[4],
                category_id=r[5],
                status=r[6],
            )
            # Extract base name of existing record dynamically
            ext_en = extract_base_name(entry.normalized_en, lang="en")
            ext_ar = extract_base_name(entry.normalized_ar, lang="ar")

            exist_base_en = ext_en.base_name.lower().strip()
            exist_base_ar = ext_ar.base_name.strip()
            from pipeline.base_name_extractor import canonical_base_name

            canonical_en = canonical_base_name(b_en, lang="en")
            existing_canonical_en = canonical_base_name(entry.normalized_en, lang="en")
            canonical_ar = canonical_base_name(b_ar, lang="ar")
            existing_canonical_ar = canonical_base_name(entry.normalized_ar, lang="ar")

            conflict = False
            # 1. Exact match of extracted base names
            if canonical_en and existing_canonical_en and canonical_en == existing_canonical_en:
                conflict = True
            elif canonical_ar and existing_canonical_ar and canonical_ar == existing_canonical_ar:
                conflict = True
            # 2. Whole-word token containment in either direction
            elif b_en and exist_base_en and not ext_en.is_generic:
                cand_words = set(entry.normalized_en.lower().split())
                exist_base_words = set(exist_base_en.split())
                if (
                    b_en in cand_words
                    or exist_base_en in b_en_words
                    or (b_en_words and b_en_words.issubset(cand_words))
                    or (exist_base_words and exist_base_words.issubset(b_en_words))
                ):
                    conflict = True
                else:
                    try:
                        from config.settings import get_settings
                        from rapidfuzz import fuzz
                        threshold = get_settings().trade_name_base_similarity_threshold
                        for ebw in exist_base_words:
                            if len(ebw) >= 4 and any(fuzz.ratio(ebw, bw) >= threshold for bw in b_en_words):
                                conflict = True
                                break
                    except ImportError:
                        pass
            elif b_ar and exist_base_ar and not ext_ar.is_generic:
                cand_ar_words = set(entry.normalized_ar.split())
                b_ar_words = set(b_ar.split())
                exist_ar_words = set(exist_base_ar.split())
                if (
                    b_ar in cand_ar_words
                    or exist_base_ar in b_ar_words
                    or (exist_ar_words and exist_ar_words.issubset(b_ar_words))
                ):
                    conflict = True

            if conflict:
                matched.append(entry)

        return matched

    async def find_similar_in_category(
        self,
        normalized_ar: str,
        normalized_en: str,
        category_id: int,
        exclude_trade_name_id: Optional[int] = None,
        similarity_threshold: float = 0.82,
    ) -> list[tuple[IndexEntry, float, str]]:
        """
        Identify confusingly similar trade names under the same activity type (category_id).
        Detects minor spelling variations, punctuation, edit distance, and phonetic similarity.
        Returns list of (IndexEntry, similarity_score, match_type) ordered by score descending.
        """
        exclude_clause = "AND trade_name_id != :exclude_id" if exclude_trade_name_id is not None else ""
        sql = f"""
            SELECT id, trade_name_id, normalized_ar, normalized_en, phonetic_key,
                   category_id, status
            FROM trade_name_index
            WHERE status IN ('active', 'reserved')
              AND category_id = :category_id
              {exclude_clause}
        """
        params = {"category_id": category_id}
        if exclude_trade_name_id is not None:
            params["exclude_id"] = exclude_trade_name_id

        result = await self._session.execute(text(sql), params)
        rows = result.fetchall()

        from pipeline.base_name_extractor import canonical_base_name

        query_base_en = canonical_base_name(normalized_en, lang="en") or ""
        query_base_ar = canonical_base_name(normalized_ar, lang="ar") or ""

        scored: list[tuple[IndexEntry, float, str]] = []

        for r in rows:
            cand_canon_ar = canonical_base_name(r[2] or "", lang="ar") or ""
            cand_canon_en = canonical_base_name(r[3] or "", lang="en") or ""

            score = 0.0

            # Compare distinctive base names so shared industry descriptors do
            # not inflate similarity and hide genuinely different brands.
            if query_base_en and cand_canon_en:
                ratio = fuzz.ratio(query_base_en, cand_canon_en) / 100.0
                token_set = fuzz.token_set_ratio(query_base_en, cand_canon_en) / 100.0
                token_sort = fuzz.token_sort_ratio(query_base_en, cand_canon_en) / 100.0
                score = max(score, ratio, 0.7 * token_set + 0.3 * token_sort)

            if query_base_ar and cand_canon_ar:
                ratio_ar = fuzz.ratio(query_base_ar, cand_canon_ar) / 100.0
                score = max(score, ratio_ar)

            # 3. Phonetic cross-check
            if r[4] and (query_base_en or query_base_ar):
                from index.phonetic import generate_phonetic_key_pair
                q_phone = generate_phonetic_key_pair(normalized_ar, normalized_en)
                if q_phone and (q_phone == r[4] or q_phone.split("|")[0] == r[4].split("|")[0]):
                    if score >= 0.75:
                        score = max(score, 0.88)

            if score >= similarity_threshold:
                match_type = "exact_duplicate" if score >= 0.99 else "spelling_variation"
                entry = IndexEntry(
                    id=r[0],
                    trade_name_id=r[1],
                    normalized_ar=r[2],
                    normalized_en=r[3],
                    phonetic_key=r[4],
                    category_id=r[5],
                    status=r[6],
                    similarity_score=round(score, 4),
                )
                scored.append((entry, round(score, 4), match_type))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # -----------------------------------------------------------------------
    # Stage ③ — Phonetic lookup (E2)
    # -----------------------------------------------------------------------
    async def lookup_phonetic(
        self,
        phonetic_key: str,
        category_id: Optional[int] = None,
        exclude_trade_name_id: Optional[int] = None,
        limit: int = 10,
    ) -> list[IndexEntry]:
        """
        Find active names that share the phonetic key (or prefix thereof), scoped by category_id if provided.
        Used for cross-script phonetic matching (E2: Noor = Nour = النور).

        The phonetic_key format is "{AR_KEY}|{EN_KEY}"; we search on both
        halves to allow Arabic query → English result and vice versa.
        """
        exclude_clause = "AND trade_name_id != :exclude_id" if exclude_trade_name_id is not None else ""
        category_clause = "AND category_id = :category_id" if category_id is not None else ""
        # Search for exact key, Arabic key prefix/containment, or English key prefix/containment
        key_parts = phonetic_key.split("|")
        ar_key = key_parts[0].strip() if len(key_parts) > 0 else phonetic_key
        en_key = key_parts[1].strip() if len(key_parts) > 1 else phonetic_key
        key_prefix = f"{ar_key}|%" if ar_key else f"{phonetic_key}|%"

        sql = f"""
            SELECT id, trade_name_id, normalized_ar, normalized_en, phonetic_key,
                   category_id, status
            FROM trade_name_index
            WHERE status = :status
              {category_clause}
              AND (
                  phonetic_key = :key
                  OR phonetic_key LIKE :key_prefix
                  OR (:ar_key != '' AND phonetic_key LIKE :ar_prefix)
                  OR (:en_key != '' AND phonetic_key LIKE :en_contains)
              )
              {exclude_clause}
            LIMIT :lim
        """
        params = {
            "status": ACTIVE_STATUS,
            "key": phonetic_key,
            "key_prefix": key_prefix,
            "ar_key": ar_key,
            "ar_prefix": f"%{ar_key}%",
            "en_key": en_key,
            "en_contains": f"%|%{en_key}%",
            "lim": limit,
        }
        if category_id is not None:
            params["category_id"] = category_id
        if exclude_trade_name_id is not None:
            params["exclude_id"] = exclude_trade_name_id

        result = await self._session.execute(text(sql), params)
        rows = result.fetchall()
        return [
            IndexEntry(
                id=r[0],
                trade_name_id=r[1],
                normalized_ar=r[2],
                normalized_en=r[3],
                phonetic_key=r[4],
                category_id=r[5],
                status=r[6],
                similarity_score=0.9,  # phonetic match gets high base score
            )
            for r in rows
        ]

    # -----------------------------------------------------------------------
    # Stage ③ — Trigram similarity (pg_trgm) — used in Phase 1 Search
    # -----------------------------------------------------------------------
    async def lookup_trigram(
        self,
        normalized_ar: str,
        normalized_en: str,
        category_id: Optional[int] = None,
        exclude_trade_name_id: Optional[int] = None,
        limit: int = 10,
    ) -> list[IndexEntry]:
        """
        Find similar active names using pg_trgm similarity, scoped by category_id if provided.
        Returns results ordered by combined AR+EN similarity score.
        Used by Stage ③ (trigram signal) and GET Search in Phase 1.
        """
        norm_ar_clean = normalized_ar.strip() if normalized_ar else ""
        norm_en_clean = normalized_en.strip().lower() if normalized_en else ""

        exclude_clause = "AND trade_name_id != :exclude_id" if exclude_trade_name_id is not None else ""
        category_clause = "AND category_id = :category_id" if category_id is not None else ""
        sql = f"""
            SELECT id, trade_name_id, normalized_ar, normalized_en, phonetic_key,
                   category_id, status,
                   GREATEST(
                       CASE WHEN :norm_ar != '' AND TRIM(normalized_ar) = :norm_ar THEN 1.0
                            WHEN :norm_ar != '' THEN LEAST(0.88, 0.4 * similarity(normalized_ar, :norm_ar) + 0.6 * word_similarity(:norm_ar, normalized_ar))
                            ELSE 0.0 END,
                       CASE WHEN :norm_en != '' AND LOWER(TRIM(normalized_en)) = :norm_en THEN 1.0
                            WHEN :norm_en != '' THEN LEAST(0.88, 0.4 * similarity(normalized_en, :norm_en) + 0.6 * word_similarity(:norm_en, normalized_en))
                            ELSE 0.0 END
                   ) AS sim_score
            FROM trade_name_index
            WHERE status = :status
              {category_clause}
              AND (
                  (:norm_ar != '' AND (TRIM(normalized_ar) = :norm_ar OR similarity(normalized_ar, :norm_ar) > 0.2 OR word_similarity(:norm_ar, normalized_ar) > 0.4))
                  OR (:norm_en != '' AND (LOWER(TRIM(normalized_en)) = :norm_en OR similarity(normalized_en, :norm_en) > 0.2 OR word_similarity(:norm_en, normalized_en) > 0.4))
              )
              {exclude_clause}
            ORDER BY sim_score DESC
            LIMIT :lim
        """
        params = {
            "status": ACTIVE_STATUS,
            "norm_ar": norm_ar_clean,
            "norm_en": norm_en_clean,
            "lim": limit,
        }
        if category_id is not None:
            params["category_id"] = category_id
        if exclude_trade_name_id is not None:
            params["exclude_id"] = exclude_trade_name_id

        try:
            result = await self._session.execute(text(sql), params)
            rows = result.fetchall()
            return [
                IndexEntry(
                    id=r[0],
                    trade_name_id=r[1],
                    normalized_ar=r[2],
                    normalized_en=r[3],
                    phonetic_key=r[4],
                    category_id=r[5],
                    status=r[6],
                    similarity_score=float(r[7]),
                )
                for r in rows
            ]
        except Exception:
            # Fallback for environments without pg_trgm extension (e.g. SQLite / local dev)
            try:
                await self._session.rollback()
            except Exception:
                pass
            import re
            from rapidfuzz import fuzz

            def _trigrams(s: str) -> set[str]:
                if not s:
                    return set()
                padded = f"  {s.strip().lower()}  "
                return set(padded[i:i+3] for i in range(len(padded) - 2))

            def _calc_trigram_sim(s1: str, s2: str) -> float:
                t1 = _trigrams(s1)
                t2 = _trigrams(s2)
                if not t1 or not t2:
                    return 0.0
                return len(t1 & t2) / len(t1 | t2)

            def _token_match(q_tok: str, c_tok: str) -> bool:
                if q_tok == c_tok:
                    return True
                # Arabic prefix normalization (ال، و، ل، ب)
                clean_q = re.sub(r"^(ال|و|ل|ب)", "", q_tok)
                clean_c = re.sub(r"^(ال|و|ل|ب)", "", c_tok)
                if clean_q and clean_c and (clean_q == clean_c or (len(clean_q) >= 3 and clean_q in clean_c) or (len(clean_c) >= 3 and clean_c in clean_q)):
                    return True
                # English substring containment or typo tolerance (>= 75% similarity)
                if len(q_tok) >= 3 and len(c_tok) >= 3:
                    if q_tok in c_tok or c_tok in q_tok:
                        return True
                    if fuzz.ratio(q_tok, c_tok) >= 75.0:
                        return True
                return False

            def _score_query_against_candidate(query: str, target: str) -> float:
                q_clean = query.strip().lower()
                t_clean = target.strip().lower()
                if not q_clean or not t_clean:
                    return 0.0
                if q_clean == t_clean:
                    return 1.0

                q_tokens = [w for w in re.findall(r"\w+", q_clean) if len(w) >= 2]
                t_tokens = [w for w in re.findall(r"\w+", t_clean) if len(w) >= 2]
                if not q_tokens or not t_tokens:
                    return 0.0

                matched_q = [qt for qt in q_tokens if any(_token_match(qt, tt) for tt in t_tokens)]
                matched_t = [tt for tt in t_tokens if any(_token_match(qt, tt) for qt in q_tokens)]

                if not matched_q:
                    # No tokens matched - check pure edit distance / trigram for close typos
                    tri = _calc_trigram_sim(q_clean, t_clean)
                    ratio = fuzz.ratio(q_clean, t_clean) / 100.0
                    if tri >= 0.25 or ratio >= 0.70:
                        return round(max(tri, ratio), 4)
                    return 0.0

                # Symmetric, length-balanced token coverage
                q_len_match = sum(len(w) for w in matched_q)
                t_len_match = sum(len(w) for w in matched_t)
                total_q_len = sum(len(w) for w in q_tokens)
                total_t_len = sum(len(w) for w in t_tokens)

                q_cov = q_len_match / total_q_len  # query coverage
                t_cov = t_len_match / total_t_len  # target coverage

                char_dice = (q_len_match + t_len_match) / (total_q_len + total_t_len)
                ratio = fuzz.ratio(q_clean, t_clean) / 100.0
                tri = _calc_trigram_sim(q_clean, t_clean)

                score = 0.45 * q_cov + 0.35 * t_cov + 0.20 * max(tri, ratio, char_dice)

                # High phrase containment reward (similar to PostgreSQL word_similarity)
                if q_clean in t_clean or (q_cov >= 0.99 and len(matched_q) >= 2):
                    phrase_boost = 0.90 + 0.08 * t_cov
                    score = max(score, phrase_boost)
                elif q_cov >= 0.99 and t_cov >= 0.99:
                    score = max(score, ratio)
                else:
                    score = min(0.88, score)

                return round(score, 4)

            sql_fallback = f"""
                SELECT id, trade_name_id, normalized_ar, normalized_en, phonetic_key,
                       category_id, status
                FROM trade_name_index
                WHERE status = :status
                  {category_clause}
                  {exclude_clause}
            """
            fallback_params = {"status": ACTIVE_STATUS}
            if category_id is not None:
                fallback_params["category_id"] = category_id
            if exclude_trade_name_id is not None:
                fallback_params["exclude_id"] = exclude_trade_name_id
            result = await self._session.execute(text(sql_fallback), fallback_params)
            rows = result.fetchall()
            scored: list[IndexEntry] = []
            for r in rows:
                score_ar = _score_query_against_candidate(norm_ar_clean, r[2] or "") if norm_ar_clean else 0.0
                score_en = _score_query_against_candidate(norm_en_clean, r[3] or "") if norm_en_clean else 0.0
                max_score = max(score_ar, score_en)

                if max_score > 0.0:
                    scored.append(
                        IndexEntry(
                            id=r[0],
                            trade_name_id=r[1],
                            normalized_ar=r[2],
                            normalized_en=r[3],
                            phonetic_key=r[4],
                            category_id=r[5],
                            status=r[6],
                            similarity_score=float(max_score),
                        )
                    )
            scored.sort(key=lambda e: e.similarity_score, reverse=True)
            return scored[:limit]

    # -----------------------------------------------------------------------
    # Stage ③ — Vector similarity (pgvector cosine) — used in Phase 2+
    # -----------------------------------------------------------------------
    async def lookup_vector(
        self,
        embedding: list[float],
        lang: str,
        category_id: Optional[int] = None,
        exclude_trade_name_id: Optional[int] = None,
        limit: int = 10,
    ) -> list[IndexEntry]:
        """
        Find similar active names using cosine similarity on pgvector embeddings, scoped by category_id if provided.
        lang: "ar" uses embedding_ar column; "en" uses embedding_en column.

        Used by Stage ③ (embedding signal) when Ai.Search = shadow/on.
        If embeddings are not yet computed for an entry, it is silently skipped.
        """
        col = "embedding_ar" if lang == "ar" else "embedding_en"
        # Build embedding literal: '[0.1, 0.2, ...]'
        vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"
        exclude_clause = "AND trade_name_id != :exclude_id" if exclude_trade_name_id is not None else ""
        category_clause = "AND category_id = :category_id" if category_id is not None else ""
        sql = f"""
            SELECT id, trade_name_id, normalized_ar, normalized_en, phonetic_key,
                   category_id, status,
                   1 - (CAST({col} AS vector) <=> CAST(:vec AS vector)) AS cos_sim
            FROM trade_name_index
            WHERE status = :status
              {category_clause}
              AND {col} IS NOT NULL
              {exclude_clause}
            ORDER BY CAST({col} AS vector) <=> CAST(:vec AS vector)
            LIMIT :lim
        """
        params = {
            "status": ACTIVE_STATUS,
            "vec": vec_literal,
            "lim": limit,
        }
        if category_id is not None:
            params["category_id"] = category_id
        if exclude_trade_name_id is not None:
            params["exclude_id"] = exclude_trade_name_id

        try:
            result = await self._session.execute(text(sql), params)
            rows = result.fetchall()
            return [
                IndexEntry(
                    id=r[0],
                    trade_name_id=r[1],
                    normalized_ar=r[2],
                    normalized_en=r[3],
                    phonetic_key=r[4],
                    category_id=r[5],
                    status=r[6],
                    similarity_score=float(r[7]),
                )
                for r in rows
            ]
        except Exception:
            # If pgvector extension is missing or casting fails, roll back aborted transaction cleanly
            try:
                await self._session.rollback()
            except Exception:
                pass
            return []

    # -----------------------------------------------------------------------
    # Stage ③ — BM25 Lexical / IDF Retrieval
    # -----------------------------------------------------------------------
    async def lookup_bm25(
        self,
        normalized_ar: str,
        normalized_en: str,
        category_id: Optional[int] = None,
        exclude_trade_name_id: Optional[int] = None,
        limit: int = 10,
    ) -> list[IndexEntry]:
        """
        Rank candidate active trade names using BM25 with Inverse Document Frequency (IDF).
        BM25 heavily rewards distinctive, rare brand tokens (e.g. 'Teja', 'Falcon')
        while attenuating frequent activity descriptors (e.g. 'Trading', 'Cafe', 'Restaurant').
        """
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            return []

        norm_ar_clean = canonical_clean(normalized_ar)
        norm_en_clean = canonical_clean(normalized_en)
        if not norm_ar_clean and not norm_en_clean:
            return []

        exclude_clause = "AND trade_name_id != :exclude_id" if exclude_trade_name_id is not None else ""
        category_clause = "AND category_id = :category_id" if category_id is not None else ""

        sql = f"""
            SELECT id, trade_name_id, normalized_ar, normalized_en, phonetic_key,
                   category_id, status
            FROM trade_name_index
            WHERE status = :status
              {category_clause}
              {exclude_clause}
        """
        params = {"status": ACTIVE_STATUS}
        if category_id is not None:
            params["category_id"] = category_id
        if exclude_trade_name_id is not None:
            params["exclude_id"] = exclude_trade_name_id

        result = await self._session.execute(text(sql), params)
        rows = result.fetchall()
        if not rows:
            return []

        # Tokenize corpus for BM25
        corpus: list[list[str]] = []
        entries: list[IndexEntry] = []

        for r in rows:
            ar_tokens = canonical_clean(r[2] or "").split()
            en_tokens = canonical_clean(r[3] or "").split()
            doc_tokens = [tok for tok in ar_tokens + en_tokens if tok]
            if not doc_tokens:
                doc_tokens = ["__empty__"]
            corpus.append(doc_tokens)
            entries.append(
                IndexEntry(
                    id=r[0],
                    trade_name_id=r[1],
                    normalized_ar=r[2],
                    normalized_en=r[3],
                    phonetic_key=r[4],
                    category_id=r[5],
                    status=r[6],
                )
            )

        bm25 = BM25Okapi(corpus)

        q_tokens = [
            tok for tok in (norm_ar_clean.split() + norm_en_clean.split())
            if tok
        ]
        if not q_tokens:
            return []

        raw_scores = bm25.get_scores(q_tokens)
        max_score = float(max(raw_scores)) if len(raw_scores) > 0 else 0.0

        if max_score <= 0.0:
            return []

        scored_entries: list[IndexEntry] = []
        for entry, score, doc_tokens in zip(entries, raw_scores, corpus):
            if score > 0.0:
                if set(q_tokens) == set(doc_tokens):
                    norm_score = 1.0
                else:
                    doc_cov = len(q_tokens) / max(1, len(doc_tokens))
                    norm_score = min(0.88, (float(score) / max_score) * (0.60 + 0.40 * min(1.0, doc_cov)))
                entry.similarity_score = round(norm_score, 4)
                scored_entries.append(entry)

        scored_entries.sort(key=lambda e: e.similarity_score, reverse=True)
        return scored_entries[:limit]


    # -----------------------------------------------------------------------
    # Stage ⑦ — Upsert (F15 index sync)
    # -----------------------------------------------------------------------
    async def upsert(
        self,
        trade_name_id: int,
        normalized_ar: str,
        normalized_en: str,
        phonetic_key: str,
        status: str,
        category_id: Optional[int] = None,
        embedding_ar: Optional[list[float]] = None,
        embedding_en: Optional[list[float]] = None,
        expiry_date=None,
    ) -> None:
        """
        Insert or update a TradeNameIndex entry.
        Called by the sync worker after processing an outbox row.

        The operation is idempotent: running it twice for the same trade_name_id
        produces the same state.
        """
        from sqlalchemy import select
        emb_ar_val = (
            "[" + ",".join(str(v) for v in embedding_ar) + "]"
            if embedding_ar else None
        )
        from pipeline.base_name_extractor import canonical_base_name, extract_base_name

        extracted_en = extract_base_name(normalized_en, lang="en")
        extracted_ar = extract_base_name(normalized_ar, lang="ar")
        base_name_en = canonical_base_name(normalized_en, lang="en")
        base_name_ar = canonical_base_name(normalized_ar, lang="ar")
        emb_en_val = (
            "[" + ",".join(str(v) for v in embedding_en) + "]"
            if embedding_en else None
        )

        stmt = select(TradeNameIndex).where(TradeNameIndex.trade_name_id == trade_name_id)
        res = await self._session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.normalized_ar = normalized_ar
            existing.normalized_en = normalized_en
            existing.phonetic_key = phonetic_key
            existing.status = status
            existing.category_id = category_id
            existing.base_name_en = base_name_en
            existing.base_name_ar = base_name_ar
            existing.embedding_ar = emb_ar_val
            existing.embedding_en = emb_en_val
            if expiry_date:
                existing.expiry_date = expiry_date
        else:
            new_entry = TradeNameIndex(
                trade_name_id=trade_name_id,
                normalized_ar=normalized_ar,
                normalized_en=normalized_en,
                phonetic_key=phonetic_key,
                status=status,
                category_id=category_id,
                base_name_en=base_name_en,
                base_name_ar=base_name_ar,
                embedding_ar=emb_ar_val,
                embedding_en=emb_en_val,
                expiry_date=expiry_date,
            )
            self._session.add(new_entry)
        await self._session.flush()

    # -----------------------------------------------------------------------
    # Stage ⑦ — Delete (F15, F21)
    # -----------------------------------------------------------------------
    async def delete(self, trade_name_id: int) -> None:
        """
        Remove a trade name from the index.
        Called by the sync worker when a trade name is deleted from the master DB.
        F21: released/rejected names removed from index so they become available.
        """
        sql = "DELETE FROM trade_name_index WHERE trade_name_id = :tid"
        await self._session.execute(text(sql), {"tid": trade_name_id})

    async def set_status(self, trade_name_id: int, new_status: str) -> None:
        """
        Update the status of an index entry without rebuilding embeddings.
        Used when a name is released or expired (status change only).
        """
        sql = """
            UPDATE trade_name_index
            SET status = :status, updated_at = now()
            WHERE trade_name_id = :tid
        """
        await self._session.execute(text(sql), {"status": new_status, "tid": trade_name_id})
