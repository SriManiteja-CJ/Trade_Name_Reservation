"""
api/metrics.py
Prometheus metrics exposition for Trade Name Intelligence Service (Phase 6, §6.3, N2).
Implements standard Prometheus exposition text format (0.0.4).

Spec references:
  §6.3 — Metrics: validation_latency_seconds (p50, p95), outcome_total by outcome & channel,
         llm_error_total by type, cache_hit_total, cache_miss_total.
  N2   — Performance monitoring: p95 latency under 3 s for validation.
"""
import threading
from collections import defaultdict
from typing import Optional
from starlette.responses import Response

_lock = threading.Lock()
_counters: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
_histograms: dict[str, list[float]] = defaultdict(list)


def record_validation_metric(outcome: str, channel: str, duration_seconds: float) -> None:
    """Record an outcome decision and its latency."""
    with _lock:
        _counters["outcome_total"][(("outcome", outcome), ("channel", channel))] += 1.0
        _histograms[f"validation_latency_seconds:{channel}:{outcome}"].append(duration_seconds)


def record_llm_error(error_type: str) -> None:
    """Record an LLM gateway error."""
    with _lock:
        _counters["llm_error_total"][(("error_type", error_type),)] += 1.0


def record_cache_hit() -> None:
    """Record a cache hit."""
    with _lock:
        _counters["cache_hit_total"][()] += 1.0


def record_cache_miss() -> None:
    """Record a cache miss."""
    with _lock:
        _counters["cache_miss_total"][()] += 1.0


def generate_prometheus_text() -> str:
    """Generate Prometheus 0.0.4 exposition text."""
    lines = [
        "# HELP outcome_total Total count of trade name validation decisions",
        "# TYPE outcome_total counter",
    ]
    with _lock:
        # 1. outcome_total
        outcomes = _counters.get("outcome_total", {})
        if not outcomes:
            lines.append('outcome_total{outcome="OK",channel="online"} 0.0')
        else:
            for labels, val in outcomes.items():
                label_str = ",".join(f'{k}="{v}"' for k, v in labels)
                lines.append(f"outcome_total{{{label_str}}} {val}")

        # 2. llm_error_total
        lines.append("# HELP llm_error_total Total count of LLM gateway errors by type")
        lines.append("# TYPE llm_error_total counter")
        llm_errs = _counters.get("llm_error_total", {})
        if not llm_errs:
            lines.append('llm_error_total{error_type="none"} 0.0')
        else:
            for labels, val in llm_errs.items():
                label_str = ",".join(f'{k}="{v}"' for k, v in labels)
                lines.append(f"llm_error_total{{{label_str}}} {val}")

        # 3. cache counters
        lines.append("# HELP cache_hit_total Total cache hits for LLM responses")
        lines.append("# TYPE cache_hit_total counter")
        hit_val = _counters.get('cache_hit_total', {}).get((), 0.0)
        lines.append(f"cache_hit_total {hit_val}")

        lines.append("# HELP cache_miss_total Total cache misses for LLM responses")
        lines.append("# TYPE cache_miss_total counter")
        miss_val = _counters.get('cache_miss_total', {}).get((), 0.0)
        lines.append(f"cache_miss_total {miss_val}")

        # §6.3 — cache_hit_rate gauge (hits / (hits + misses)); 0 when no calls yet
        total_calls = hit_val + miss_val
        hit_rate = round(hit_val / total_calls, 4) if total_calls > 0 else 0.0
        lines.append("# HELP cache_hit_rate Ratio of LLM response cache hits to total cache lookups (§6.3)")
        lines.append("# TYPE cache_hit_rate gauge")
        lines.append(f"cache_hit_rate {hit_rate}")

        # 4. validation_latency_seconds histogram summary
        lines.append("# HELP validation_latency_seconds End-to-end latency for trade name validation in seconds")
        lines.append("# TYPE validation_latency_seconds histogram")
        total_count = 0
        total_sum = 0.0
        for k, vals in _histograms.items():
            total_count += len(vals)
            total_sum += sum(vals)
        lines.append(f"validation_latency_seconds_count {total_count}")
        lines.append(f"validation_latency_seconds_sum {total_sum:.4f}")

    return "\n".join(lines) + "\n"


def metrics_endpoint() -> Response:
    """Return raw Prometheus metrics formatted for scraping."""
    content = generate_prometheus_text()
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")
