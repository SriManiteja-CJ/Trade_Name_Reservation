"""
pipeline/retriever.py
Stage ③ Hybrid Similarity Retriever for Trade Name Intelligence Service.

Combines:
  1. Dense vector embedding similarity (TEI / cosine)
  2. Cross-script phonetic key matching (E2: Noor = Nour = النور)
  3. Sparse character trigram similarity (pg_trgm / RapidFuzz)

Spec references:
  F3   — Similarity check against existing names
  F19  — Keyword search over trade names
  F22  — Search keywords stored/queried in both languages
  E2   — Phonetic + embedding matching
  E8   — Fuzzy, cross-language search
  §3.1 Stage ③ — Hybrid Search architecture
"""
import logging
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import FlagMode, get_settings
from index.phonetic import generate_phonetic_key_pair
from index.repository import IndexEntry, TradeNameIndexRepository
from pipeline.normalizer import normalize_arabic, normalize_english

logger = logging.getLogger(__name__)
settings = get_settings()


class HybridRetriever:
    """
    Stage ③ Hybrid Retriever combining vector, phonetic, and trigram signals.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TradeNameIndexRepository(session)

    async def retrieve(
        self,
        *,
        normalized_ar: str,
        normalized_en: str,
        category_id: Optional[int] = None,
        exclude_trade_name_id: Optional[int] = None,
        limit: int = 10,
    ) -> list[IndexEntry]:
        """
        Execute hybrid retrieval across active names (optionally scoped to category_id).

        Fuses trigram, phonetic, and vector signals with rank scoring.
        """
        entries_by_id: dict[int, IndexEntry] = {}
        scores_by_id: dict[int, dict[str, float]] = {}

        # -----------------------------------------------------------------
        # 1. Trigram Retrieval (Surface / Lexical Similarity)
        # -----------------------------------------------------------------
        try:
            trigram_hits = await self.repo.lookup_trigram(
                normalized_ar=normalized_ar,
                normalized_en=normalized_en,
                category_id=category_id,
                exclude_trade_name_id=exclude_trade_name_id,
                limit=limit * 2,
            )
            for hit in trigram_hits:
                entries_by_id[hit.trade_name_id] = hit
                scores_by_id.setdefault(hit.trade_name_id, {})["trigram"] = hit.similarity_score
        except Exception as exc:
            logger.debug("trigram_lookup_failed", extra={"error": str(exc)})

        # -----------------------------------------------------------------
        # 2. BM25 Retrieval (IDF-Weighted Lexical Distinctiveness)
        # -----------------------------------------------------------------
        try:
            bm25_hits = await self.repo.lookup_bm25(
                normalized_ar=normalized_ar,
                normalized_en=normalized_en,
                category_id=category_id,
                exclude_trade_name_id=exclude_trade_name_id,
                limit=limit * 2,
            )
            for hit in bm25_hits:
                if hit.trade_name_id not in entries_by_id:
                    entries_by_id[hit.trade_name_id] = hit
                scores_by_id.setdefault(hit.trade_name_id, {})["bm25"] = hit.similarity_score
        except Exception as exc:
            logger.debug("bm25_lookup_failed", extra={"error": str(exc)})

        # -----------------------------------------------------------------
        # 3. Phonetic Retrieval (Cross-script pronunciation, E2)
        # -----------------------------------------------------------------
        phonetic_key = generate_phonetic_key_pair(normalized_ar, normalized_en)
        if phonetic_key:
            try:
                phonetic_hits = await self.repo.lookup_phonetic(
                    phonetic_key=phonetic_key,
                    category_id=category_id,
                    exclude_trade_name_id=exclude_trade_name_id,
                    limit=limit * 2,
                )
                for hit in phonetic_hits:
                    if hit.trade_name_id not in entries_by_id:
                        entries_by_id[hit.trade_name_id] = hit
                    scores_by_id.setdefault(hit.trade_name_id, {})["phonetic"] = hit.similarity_score
            except Exception as exc:
                logger.debug("phonetic_lookup_failed", extra={"error": str(exc)})

        # -----------------------------------------------------------------
        # 4. Dense Vector Retrieval (when ai_search != off)
        # -----------------------------------------------------------------
        if settings.ai_search != FlagMode.off:
            try:
                embedding = await self._compute_embedding(normalized_ar or normalized_en)
                if embedding:
                    lang = "ar" if normalized_ar else "en"
                    vector_hits = await self.repo.lookup_vector(
                        embedding=embedding,
                        lang=lang,
                        category_id=category_id,
                        exclude_trade_name_id=exclude_trade_name_id,
                        limit=limit * 2,
                    )
                    for hit in vector_hits:
                        if hit.trade_name_id not in entries_by_id:
                            entries_by_id[hit.trade_name_id] = hit
                        scores_by_id.setdefault(hit.trade_name_id, {})["vector"] = hit.similarity_score
            except Exception as exc:
                logger.debug("vector_lookup_failed", extra={"error": str(exc)})

        # -----------------------------------------------------------------
        # 5. Score Fusion (Mathematically Sound Multi-Channel Fusion)
        # -----------------------------------------------------------------
        results: list[IndexEntry] = []
        norm_ar_clean = normalized_ar.strip() if normalized_ar else ""
        norm_en_clean = normalized_en.strip().lower() if normalized_en else ""

        for tid, entry in entries_by_id.items():
            s = scores_by_id.get(tid, {})
            score_tri = float(s.get("trigram", 0.0))
            score_bm25 = float(s.get("bm25", 0.0))
            score_pho = float(s.get("phonetic", 0.0))
            score_vec = float(s.get("vector", 0.0))

            entry_ar_clean = entry.normalized_ar.strip() if entry.normalized_ar else ""
            entry_en_clean = entry.normalized_en.strip().lower() if entry.normalized_en else ""

            # Rule 1: Exact Lexical Match receives highest score (1.0 = 100%)
            is_exact_en = bool(norm_en_clean and entry_en_clean and norm_en_clean == entry_en_clean)
            is_exact_ar = bool(norm_ar_clean and entry_ar_clean and norm_ar_clean == entry_ar_clean)

            if is_exact_en or is_exact_ar:
                entry.similarity_score = 1.0
                results.append(entry)
                continue

            # Rule 2: Token-Order Invariant Match (exact token set rearranged, e.g. "teja cafe" == "cafe teja")
            toks_q_en = set(norm_en_clean.split()) if norm_en_clean else set()
            toks_e_en = set(entry_en_clean.split()) if entry_en_clean else set()
            toks_q_ar = set(norm_ar_clean.split()) if norm_ar_clean else set()
            toks_e_ar = set(entry_ar_clean.split()) if entry_ar_clean else set()

            if (toks_q_en and toks_q_en == toks_e_en) or (toks_q_ar and toks_q_ar == toks_e_ar):
                entry.similarity_score = 1.0
                results.append(entry)
                continue

            # Rule 3: Dynamic Multi-Channel Signal Fusion
            # Active weights dynamically adapt based on available modalities
            lexical_best = max(score_tri, score_bm25)
            active_weights = {"lexical": 0.50}
            active_signals = {"lexical": lexical_best}

            if score_bm25 > 0.0:
                active_weights["bm25"] = 0.20
                active_signals["bm25"] = score_bm25

            if score_pho > 0.0:
                active_weights["phonetic"] = 0.15
                active_signals["phonetic"] = score_pho

            if score_vec > 0.0:
                active_weights["vector"] = 0.15
                active_signals["vector"] = score_vec

            total_weight = sum(active_weights.values())
            weighted_avg = sum(active_weights[k] * active_signals[k] for k in active_weights) / total_weight

            # Reward cross-modal confirmation (e.g., both phonetic and lexical match)
            if (score_tri > 0.50 or score_bm25 > 0.50) and score_pho > 0.50:
                weighted_avg = min(0.92, weighted_avg * 1.15)

            # Final similarity score for non-exact partial containment is capped at 0.88
            final_score = max(score_tri, score_bm25, weighted_avg)
            entry.similarity_score = round(min(0.88, max(0.0, final_score)), 4)
            results.append(entry)

        # Sort descending by combined similarity score
        results.sort(key=lambda e: e.similarity_score, reverse=True)
        return results[:limit]

    async def search_keyword(
        self,
        keyword: str,
        limit: int = 10,
    ) -> list[IndexEntry]:
        """
        F19 / E8: Keyword search with dual-language normalization (F22)
        and cross-language transliteration expansion.
        """
        norm_ar = normalize_arabic(keyword)
        norm_en = normalize_english(keyword)

        # Cross-language expansion for keyword search (E8 / F22):
        # When single-language keyword is entered, transliterate across scripts to search both AR & EN indexes
        try:
            from api.routes.trade_name import _heuristic_transliterate, _heuristic_transliterate_ar_to_en
            if any('a' <= c <= 'z' for c in norm_en) and not any('\u0600' <= c <= '\u06FF' for c in keyword):
                ar_translit = _heuristic_transliterate(norm_en).strip()
                if ar_translit:
                    norm_ar = ar_translit
            elif any('\u0600' <= c <= '\u06FF' for c in keyword) and not any('a' <= c <= 'z' for c in norm_en):
                en_translit = _heuristic_transliterate_ar_to_en(keyword).strip().lower()
                if en_translit:
                    norm_en = en_translit
        except Exception:
            pass

        return await self.retrieve(
            normalized_ar=norm_ar,
            normalized_en=norm_en,
            limit=limit,
        )

    async def _compute_embedding(self, text: str) -> Optional[list[float]]:
        """
        Compute embedding vector from TEI server if reachable, or from active provider.
        """
        if not text:
            return None
        # 1. Attempt HuggingFace TEI server if configured
        tei_url = getattr(settings, "tei_base_url", None)
        if tei_url:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    res = await client.post(
                        f"{tei_url}/embed",
                        json={"inputs": [text]},
                    )
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, list) and len(data) > 0:
                            return data[0]
            except Exception:
                pass

        # 2. Attempt OpenAI / Ollama embedding endpoint if configured
        try:
            base_url = settings.effective_llm_base_url
            api_key = settings.effective_api_key
            if "openai" in base_url or "localhost:11434" in base_url:
                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                async with httpx.AsyncClient(timeout=1.5) as client:
                    model = "text-embedding-3-small" if "openai" in base_url else "nomic-embed-text"
                    res = await client.post(
                        f"{base_url}/embeddings",
                        headers=headers,
                        json={"input": text, "model": model},
                    )
                    if res.status_code == 200:
                        data = res.json()
                        if "data" in data and len(data["data"]) > 0:
                            return data["data"][0]["embedding"]
        except Exception:
            pass

        return None
