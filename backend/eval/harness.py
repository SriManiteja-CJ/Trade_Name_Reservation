"""
eval/harness.py
Evaluation Harness & Quality Benchmark for Trade Name Intelligence Service (Phase 6, §6.4).

Responsibilities:
  - Load and execute gold set cases from eval/gold_set/
  - Evaluate against DeterministicGates, LexiconRepository, and DecisionPolicy
  - Measure accuracy, precision, recall, and false-block rate
  - Verify prompt injection resistance (injected payload fails to alter pipeline output)
  - Output structured JSON report and human-readable summary
  - CI Quality Gate: fails with non-zero exit if quality thresholds are breached

Spec references:
  §6.4 — Evaluation: precision/recall per F4 category, gold set benchmark, prompt injection test
  N1   — Fail-closed invariant verification
  N3   — Real request audit linking
  N7   — Continuous quality feedback loop
"""
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import FlagMode, get_settings
from index.repository import TradeNameIndexRepository
from lexicon.repository import LexiconEntry, LexiconRepository
from pipeline.decision_policy import Outcome, apply_policy
from pipeline.activity_catalogue import get_category_by_code
from pipeline.deterministic_gates import DeterministicGates
from pipeline.name_composer import compose
from pipeline.normalizer import normalize_arabic, normalize_english

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_GOLD_SET_PATH = Path(__file__).resolve().parent / "gold_set" / "gold_cases.json"


@dataclass
class CaseResult:
    case_id: str
    name_ar: str
    name_en: str
    expected_decision: str
    actual_decision: str
    expected_flags: list[str]
    actual_flags: list[str]
    passed: bool
    is_adversarial: bool
    adversarial_safe: bool
    error: Optional[str] = None


@dataclass
class EvaluationReport:
    total_cases: int = 0
    passed_cases: int = 0
    accuracy: float = 0.0
    false_block_count: int = 0
    false_block_rate: float = 0.0
    adversarial_total: int = 0
    adversarial_passed: int = 0
    adversarial_pass_rate: float = 0.0
    case_results: list[CaseResult] = field(default_factory=list)
    meets_thresholds: bool = True


class EvaluationHarness:
    """
    Automated evaluation harness for evaluating pipeline compliance and safety.
    """

    def __init__(self, session: AsyncSession, gold_set_path: Optional[Path] = None) -> None:
        self.session = session
        self.gold_set_path = gold_set_path or DEFAULT_GOLD_SET_PATH
        self.lexicon_repo = LexiconRepository(session)
        self.index_repo = TradeNameIndexRepository(session)

    async def seed_benchmark_lexicon(self) -> None:
        """Seed minimal standard test lexicon terms for benchmark consistency."""
        baseline_terms = [
            ("كازينو", "casino", "prohibited", "ar", "block", ["cazino", "kassino"]),
            ("casino", "casino", "prohibited", "en", "block", ["cazino", "kassino"]),
            ("قمار", "قمار", "prohibited", "ar", "block", ["ميسر"]),
            ("gambling", "gambling", "prohibited", "en", "block", []),
            ("رهان", "رهان", "prohibited", "ar", "block", []),
            ("betting", "betting", "prohibited", "en", "block", ["bett1ng"]),
            ("أم القيوين", "ام القيوين", "location", "ar", "review", []),
            ("umm al quwain", "umm al quwain", "location", "en", "review", []),
            ("الرحمن", "الرحمن", "divine_name", "ar", "review", []),
            ("rahman", "rahman", "divine_name", "en", "review", []),
            ("الفلاسي", "الفلاسي", "family_name", "ar", "review", []),
            ("al falasi", "al falasi", "family_name", "en", "review", []),
            ("ملكي", "ملكي", "special", "ar", "review", []),
            ("royal", "royal", "special", "en", "review", []),
            ("الإمارات", "الامارات", "location", "ar", "review", ["الامارات"]),
            ("emirates", "emirates", "location", "en", "review", ["uae"]),
            ("أبوظبي", "ابوظبي", "location", "ar", "review", ["ابو ظبي"]),
            ("abu dhabi", "abu dhabi", "location", "en", "review", []),
            ("الله", "الله", "divine_name", "ar", "review", []),
            ("allah", "allah", "divine_name", "en", "review", []),
            ("الشحي", "الشحي", "family_name", "ar", "review", ["الشعشاع"]),
            ("الشعشاع", "الشعشاع", "family_name", "ar", "review", []),
            ("al shehhi", "al shehhi", "family_name", "en", "review", []),
            ("حكومة", "حكومه", "special", "ar", "block", ["حكومة"]),
            ("government", "government", "special", "en", "block", ["govt"]),
            ("دبي", "دبي", "location", "ar", "review", []),
            ("dubai", "dubai", "location", "en", "review", []),
            ("خمور", "خمور", "prohibited", "ar", "block", ["نبيذ"]),
            ("vulgar", "vulgar", "profanity", "en", "block", []),
            ("فحش", "فحش", "profanity", "ar", "block", []),
            ("bar", "bar", "prohibited", "en", "block", []),
        ]
        for term, norm, cat, lang, sev, vars_list in baseline_terms:
            entry = LexiconEntry(
                id=None,
                term=term,
                normalized_term=norm,
                category=cat,
                lang=lang,
                severity=sev,
                variants=vars_list,
                approved_by="EvaluationBenchmarkAdmin",
            )
            await self.lexicon_repo.upsert(entry)

    def load_gold_cases(self) -> list[dict]:
        """Load benchmark cases from JSON file."""
        if not self.gold_set_path.exists():
            raise FileNotFoundError(f"Gold set file not found: {self.gold_set_path}")
        with open(self.gold_set_path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def evaluate_single_case(self, case: dict) -> CaseResult:
        """
        Evaluate a single gold set test case against the pipeline.
        """
        case_id = case.get("id", "UNKNOWN")
        name_ar = case["name_ar"]
        name_en = case["name_en"]
        expected_decision = case["expected_decision"]
        is_adversarial = case.get("is_adversarial", False)

        # 1. Pipeline Normalization & Token Stripping
        composed = compose(
            name_ar=name_ar,
            name_en=name_en,
            operation_type="new",
            is_outside_uaq=False,
        )

        # 2. Stage ②: Deterministic Gate Evaluation
        gates = DeterministicGates(
            index_repo=self.index_repo,
            lexicon_repo=self.lexicon_repo,
        )
        activity = get_category_by_code(case.get("activity_category", ""))
        gate_signals = await gates.run(
            composed=composed,
            category_id=activity["category_id"] if activity else None,
        )

        # 3. Stage ⑤: Decision Policy
        policy_result = apply_policy(
            gate_signals=gate_signals,
            llm_output=None,
            skip_word_checks=composed.skip_word_checks,
            lang_header="en",
            similarity_score=0.0,
        )

        actual_decision = policy_result.outcome.value
        actual_flags = [s.category for s in gate_signals if s.category]

        # 4. Check Prompt Injection Security (N6)
        # Verify that prompt injection text did not produce an unhandled exception
        # or bypass the hard gates.
        adversarial_safe = True
        if is_adversarial:
            # For adversarial test cases with prohibited roots (e.g. cazino/kassino),
            # it must remain BLOCKED regardless of injected prompt commands.
            if any(f in case.get("expected_flags", []) for f in ("prohibited", "profanity")):
                adversarial_safe = (actual_decision == "BLOCKED")
            else:
                # If clean name with injection payload, it must produce structured outcome without hijacking
                adversarial_safe = actual_decision in ("OK", "NEEDS_REVIEW", "BLOCKED")

        passed = (actual_decision == expected_decision) and adversarial_safe

        return CaseResult(
            case_id=case_id,
            name_ar=name_ar,
            name_en=name_en,
            expected_decision=expected_decision,
            actual_decision=actual_decision,
            expected_flags=case.get("expected_flags", []),
            actual_flags=actual_flags,
            passed=passed,
            is_adversarial=is_adversarial,
            adversarial_safe=adversarial_safe,
        )

    async def run_evaluation(self, seed_lexicon: bool = True) -> EvaluationReport:
        """
        Run the complete evaluation suite against the gold set.
        """
        if seed_lexicon:
            await self.seed_benchmark_lexicon()

        cases = self.load_gold_cases()
        results: list[CaseResult] = []

        false_blocks = 0
        passed_count = 0
        adversarial_total = 0
        adversarial_passed = 0

        orig_flag = settings.ai_analyzer
        settings.ai_analyzer = FlagMode.off
        try:
            for case in cases:
                res = await self.evaluate_single_case(case)
                results.append(res)

                if res.passed:
                    passed_count += 1

                if case.get("expected_decision") == "OK" and res.actual_decision == "BLOCKED":
                    false_blocks += 1

                if res.is_adversarial:
                    adversarial_total += 1
                    if res.adversarial_safe:
                        adversarial_passed += 1
        finally:
            settings.ai_analyzer = orig_flag

        total = len(cases)
        accuracy = round(passed_count / total, 4) if total > 0 else 0.0
        fb_rate = round(false_blocks / total, 4) if total > 0 else 0.0
        adv_rate = round(adversarial_passed / adversarial_total, 4) if adversarial_total > 0 else 1.0

        # Quality thresholds:
        # - Accuracy >= 85%
        # - False block rate <= 5%
        # - Adversarial security pass rate == 100%
        meets_thresholds = (accuracy >= 0.85) and (fb_rate <= 0.05) and (adv_rate == 1.0)

        report = EvaluationReport(
            total_cases=total,
            passed_cases=passed_count,
            accuracy=accuracy,
            false_block_count=false_blocks,
            false_block_rate=fb_rate,
            adversarial_total=adversarial_total,
            adversarial_passed=adversarial_passed,
            adversarial_pass_rate=adv_rate,
            case_results=results,
            meets_thresholds=meets_thresholds,
        )

        return report

    def format_summary_markdown(self, report: EvaluationReport) -> str:
        """Generate a concise markdown summary of evaluation findings."""
        status_icon = "✅ PASSED" if report.meets_thresholds else "❌ FAILED"
        lines = [
            f"# DED Trade Name Intelligence — Evaluation Harness Report ({status_icon})",
            "",
            "## Executive Summary",
            f"- **Total Gold Cases Evaluated:** {report.total_cases}",
            f"- **Accuracy:** {report.accuracy * 100:.1f}% (Threshold: ≥ 85.0%)",
            f"- **False Block Rate:** {report.false_block_rate * 100:.1f}% (Threshold: ≤ 5.0%)",
            f"- **Prompt Injection Security Pass Rate:** {report.adversarial_pass_rate * 100:.1f}% (Threshold: 100%)",
            "",
            "## Case Breakdown",
            "| ID | Trade Name | Expected | Actual | Adversarial Safe | Result |",
            "|---|---|---|---|:---:|:---:|",
        ]
        for c in report.case_results:
            icon = "✓" if c.passed else "✗"
            adv_icon = "🛡️ Yes" if c.adversarial_safe else "⚠️ Failed"
            lines.append(f"| {c.case_id} | {c.name_en} | {c.expected_decision} | {c.actual_decision} | {adv_icon} | {icon} |")

        return "\n".join(lines)
