from __future__ import annotations

from typing import Any

from backend.config import get_settings
from backend.evaluation.benchmark_expectations import BenchmarkExpectationEvaluator
from backend.evaluation.llm_judge import LLMJudgeEvaluator
from backend.evaluation.metrics import combine_evaluations
from backend.evaluation.rule_based import RuleBasedEvaluator
from backend.llm import is_llm_configured
from backend.models.schemas import BenchmarkExpectation, EvaluationProvenance, EvaluationResult


class EvaluationService:
    """Single evaluation path used by API evaluation, regression, and optimisation."""

    def __init__(self) -> None:
        self.rule_evaluator = RuleBasedEvaluator()
        self.expectation_evaluator = BenchmarkExpectationEvaluator()
        self.judge_evaluator = LLMJudgeEvaluator()

    def evaluate(
        self,
        *,
        agent_type: str,
        full_input: dict[str, Any],
        output: dict[str, Any],
        latency_ms: float,
        token_usage: dict[str, Any] | None,
        agent_model: str | None,
        expected: BenchmarkExpectation | dict[str, Any] | None = None,
    ) -> EvaluationResult:
        expectation = expected if expected is not None else full_input.get("expected")
        rule_scores = self.rule_evaluator.evaluate(output)
        expectation_score = self.expectation_evaluator.evaluate(output, expectation)
        judge_scores = self.judge_evaluator.evaluate(
            agent_type=agent_type,
            full_input=full_input,
            output=output,
            agent_model=agent_model,
        )

        settings = get_settings()
        judge_enabled = is_llm_configured(settings)
        judge_is_distinct = (
            settings.openai_judge_model != agent_model if agent_model else None
        )
        caveat: str | None = None
        if judge_enabled and judge_is_distinct is False:
            caveat = (
                "Agent and judge use the same model deployment; deterministic rule and "
                "benchmark checks remain guardrails, but self-evaluation bias is possible."
            )
        elif not judge_enabled:
            caveat = "LLM judge is disabled; neutral placeholder scores are used."

        provenance = EvaluationProvenance(
            benchmark_checks_enabled=expectation_score is not None,
            llm_judge_enabled=judge_enabled,
            llm_provider=settings.llm_provider if judge_enabled else None,
            agent_model=agent_model,
            judge_model=settings.openai_judge_model if judge_enabled else None,
            judge_is_distinct=judge_is_distinct if judge_enabled else None,
            caveat=caveat,
        )
        return combine_evaluations(
            rule_scores=rule_scores,
            judge_scores=judge_scores,
            latency_ms=latency_ms,
            token_usage=token_usage,
            benchmark_expectations=expectation_score,
            provenance=provenance,
        )
