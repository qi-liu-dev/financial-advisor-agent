from __future__ import annotations

from statistics import pstdev
from typing import Any

from backend.config import get_settings
from backend.evaluation.llm_judge import JudgeEvaluation
from backend.models.schemas import (
    EvaluationProvenance,
    EvaluationResult,
    MetricScore,
    OptimisationMetrics,
)


def estimate_cost(token_usage: dict[str, Any] | None) -> float:
    if not token_usage:
        return 0.0

    settings = get_settings()
    input_tokens = (
        token_usage.get("prompt_tokens")
        or token_usage.get("input_tokens")
        or token_usage.get("prompt_token_count")
        or 0
    )
    output_tokens = (
        token_usage.get("completion_tokens")
        or token_usage.get("output_tokens")
        or token_usage.get("completion_token_count")
        or 0
    )
    return (
        input_tokens * settings.estimated_input_cost_per_1m_tokens
        + output_tokens * settings.estimated_output_cost_per_1m_tokens
    ) / 1_000_000


def combine_evaluations(
    *,
    rule_scores: dict[str, MetricScore],
    judge_scores: JudgeEvaluation,
    latency_ms: float,
    token_usage: dict[str, Any] | None,
    benchmark_expectations: MetricScore | None = None,
    provenance: EvaluationProvenance | None = None,
) -> EvaluationResult:
    return EvaluationResult(
        faithfulness=judge_scores.faithfulness,
        completeness=judge_scores.completeness,
        risk_awareness=_lower_score(
            judge_scores.risk_awareness,
            rule_scores.get("risk_awareness"),
        ),
        clarity=_lower_score(judge_scores.clarity, rule_scores.get("clarity")),
        advisor_usefulness=judge_scores.advisor_usefulness,
        safety=_lower_score(judge_scores.safety, rule_scores.get("safety")),
        format_correctness=rule_scores["format_correctness"],
        benchmark_expectations=benchmark_expectations,
        latency_ms=latency_ms,
        estimated_cost=estimate_cost(token_usage),
        feedback=judge_scores.feedback,
        provenance=provenance,
    )


def evaluation_quality_score(score: EvaluationResult) -> float:
    fields = [
        score.faithfulness.score,
        score.completeness.score,
        score.risk_awareness.score,
        score.clarity.score,
        score.advisor_usefulness.score,
        score.format_correctness.score,
    ]
    if score.benchmark_expectations is not None:
        fields.append(score.benchmark_expectations.score)
    return sum(fields) / len(fields)


def average_quality(scores: list[EvaluationResult]) -> OptimisationMetrics:
    if not scores:
        return OptimisationMetrics(
            quality=0.0,
            quality_stddev=0.0,
            safety=0.0,
            safety_stddev=0.0,
            latency_ms=0.0,
            latency_ms_stddev=0.0,
            estimated_cost=0.0,
            estimated_cost_stddev=0.0,
            sample_count=0,
        )

    quality_values = [evaluation_quality_score(score) for score in scores]
    safety_values = [float(score.safety.score) for score in scores]
    latency_values = [score.latency_ms for score in scores]
    cost_values = [score.estimated_cost for score in scores]
    return OptimisationMetrics(
        quality=round(_mean(quality_values), 3),
        quality_stddev=round(_stddev(quality_values), 3),
        safety=round(_mean(safety_values), 3),
        safety_stddev=round(_stddev(safety_values), 3),
        latency_ms=round(_mean(latency_values), 3),
        latency_ms_stddev=round(_stddev(latency_values), 3),
        estimated_cost=round(_mean(cost_values), 8),
        estimated_cost_stddev=round(_stddev(cost_values), 8),
        sample_count=len(scores),
    )


def _lower_score(primary: MetricScore, secondary: MetricScore | None) -> MetricScore:
    if secondary is None or primary.score <= secondary.score:
        return primary
    return MetricScore(
        score=secondary.score,
        feedback=f"{primary.feedback} Rule-based check: {secondary.feedback}",
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _stddev(values: list[float]) -> float:
    return pstdev(values) if len(values) > 1 else 0.0
