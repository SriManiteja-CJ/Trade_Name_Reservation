"""
audit/repository.py
Repository for reading and writing AiDecisionAudit records (N3).

Spec references:
  N3 — Every AI decision auditable, linked to the real request ID
  N6 — Input hash used instead of storing unnecessary sensitive raw data
  §5.1 — ai_decision_audit table schema
"""
import hashlib
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AiDecisionAudit


def compute_input_hash(
    normalized_ar: str,
    normalized_en: str,
    category_id: Optional[int] = None,
    legal_form: Optional[str] = None,
) -> str:
    """
    Compute a SHA-256 hash of the normalized input components (N6).
    Ensures reproducible audit linkage without exposing raw PII directly in indexes.
    """
    raw_payload = f"{normalized_ar.strip()}||{normalized_en.strip()}||{category_id or ''}||{legal_form or ''}"
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()


class AuditRepository:
    """Async repository for AiDecisionAudit table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_audit(
        self,
        request_id: str,
        channel: str,
        input_hash: str,
        prompt_version: str,
        model_id: str,
        outcome: str,
        raw_output: Optional[dict[str, Any]] = None,
        latency_ms: Optional[int] = None,
        tokens: Optional[int] = None,
    ) -> AiDecisionAudit:
        """
        Record an AI decision audit entry (N3).
        """
        audit_entry = AiDecisionAudit(
            request_id=request_id,
            channel=channel.lower() if channel else "online",
            input_hash=input_hash,
            prompt_version=prompt_version,
            model_id=model_id,
            raw_output=raw_output,
            outcome=outcome,
            latency_ms=latency_ms,
            tokens=tokens,
        )
        self.session.add(audit_entry)
        await self.session.flush()
        return audit_entry

    async def get_by_request_id(self, request_id: str) -> list[AiDecisionAudit]:
        """
        Retrieve all audit entries for a specific DED request ID.
        """
        stmt = (
            select(AiDecisionAudit)
            .where(AiDecisionAudit.request_id == request_id)
            .order_by(AiDecisionAudit.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
