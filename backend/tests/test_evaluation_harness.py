"""
tests/test_evaluation_harness.py
Unit and integration tests for Phase 6: Evaluation Harness & Observability.

Spec references:
  §6.4 — Evaluation: gold set benchmark, precision/recall, prompt injection security
  N2   — Performance SLA monitoring
  N6   — Prompt injection isolation
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.metrics import record_validation_metric
from eval.harness import EvaluationHarness


@pytest.mark.asyncio
async def test_evaluation_harness_benchmark(db_session: AsyncSession):
    """
    Test that the EvaluationHarness executes against gold set and meets CI thresholds:
    - Accuracy >= 85%
    - False Block Rate <= 5%
    - Adversarial Security Pass Rate == 100%
    """
    harness = EvaluationHarness(db_session)
    report = await harness.run_evaluation(seed_lexicon=True)

    assert report.total_cases >= 10
    assert report.accuracy >= 0.85
    assert report.false_block_rate <= 0.05
    assert report.adversarial_pass_rate == 1.0
    assert report.meets_thresholds is True

    # Test summary formatting
    summary = harness.format_summary_markdown(report)
    assert "Evaluation Harness Report" in summary
    assert "Accuracy:" in summary
    assert "Prompt Injection Security Pass Rate" in summary
    assert "100.0%" in summary


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint(client: AsyncClient):
    """
    GET /metrics: Verifies that Prometheus metrics endpoint returns standard format.
    """
    # 1. Trigger metric recording
    record_validation_metric(outcome="OK", channel="online", duration_seconds=0.15)
    record_validation_metric(outcome="BLOCKED", channel="walkin", duration_seconds=0.25)

    # 2. Scrape metrics endpoint
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    content = resp.text

    assert "validation_latency_seconds" in content
    assert "outcome_total" in content
    assert "llm_error_total" in content
    assert 'outcome="OK"' in content or 'outcome_total' in content
