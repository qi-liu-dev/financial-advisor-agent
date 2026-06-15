from __future__ import annotations

from typing import Any

from backend.config import get_settings
from backend.evaluation.llm_judge import JudgeEvaluation
from backend.models.schemas import EvaluationResult, MetricScore


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
) -> EvaluationResult:
    return EvaluationResult(
        faithfulness=judge_scores.faithfulness,
        completeness=judge_scores.completeness,
        risk_awareness=_lower_score(judge_scores.risk_awareness, rule_scores.get("risk_awareness")),
        clarity=_lower_score(judge_scores.clarity, rule_scores.get("clarity")),
        advisor_usefulness=judge_scores.advisor_usefulness,
        safety=_lower_score(judge_scores.safety, rule_scores.get("safety")),
        format_correctness=rule_scores["format_correctness"],
        benchmark_expectations=benchmark_expectations,
        latency_ms=latency_ms,
        estimated_cost=estimate_cost(token_usage),
        feedback=judge_scores.feedback,
    )


def average_quality(scores: list[EvaluationResult]) -> dict[str, float]:
    if not scores:
        return {
            "quality": 0.0,
            "safety": 0.0,
            "latency_ms": 0.0,
            "estimated_cost": 0.0,
        }

    quality_fields = [
        "faithfulness",
        "completeness",
        "risk_awareness",
        "clarity",
        "advisor_usefulness",
        "format_correctness",
    ]
    quality_scores = [
        getattr(score, field).score for score in scores for field in quality_fields
    ]
    quality_scores.extend(
        score.benchmark_expectations.score
        for score in scores
        if score.benchmark_expectations is not None
    )
    quality = sum(quality_scores) / len(quality_scores)
    return {
        "quality": round(quality, 3),
        "safety": round(sum(score.safety.score for score in scores) / len(scores), 3),
        "latency_ms": round(sum(score.latency_ms for score in scores) / len(scores), 3),
        "estimated_cost": round(sum(score.estimated_cost for score in scores) / len(scores), 8),
    }


def _lower_score(primary: MetricScore, secondary: MetricScore | None) -> MetricScore:
    if secondary is None or primary.score <= secondary.score:
        return primary
    return MetricScore(
        score=secondary.score,
        feedback=f"{primary.feedback} Rule-based check: {secondary.feedback}",
    )
