from __future__ import annotations

from backend.evaluation.metrics import average_quality
from backend.models.schemas import EvaluationResult, MetricScore, OptimisationMetrics
from backend.optimisation.pareto import (
    PromptCandidate,
    SelectionPolicy,
    select_candidates_with_policy,
)


def _score(value: int) -> MetricScore:
    return MetricScore(score=value, feedback="test")


def _evaluation(
    *,
    score: int,
    safety: int,
    latency_ms: float,
    cost: float,
) -> EvaluationResult:
    return EvaluationResult(
        faithfulness=_score(score),
        completeness=_score(score),
        risk_awareness=_score(score),
        clarity=_score(score),
        advisor_usefulness=_score(score),
        safety=_score(safety),
        format_correctness=_score(score),
        benchmark_expectations=_score(score),
        latency_ms=latency_ms,
        estimated_cost=cost,
        feedback="test",
    )


def _metrics(
    quality: float,
    safety: float,
    latency: float,
    cost: float,
) -> OptimisationMetrics:
    return OptimisationMetrics(
        quality=quality,
        quality_stddev=0.1,
        safety=safety,
        safety_stddev=0.0,
        latency_ms=latency,
        latency_ms_stddev=50.0,
        estimated_cost=cost,
        estimated_cost_stddev=0.00001,
        sample_count=6,
    )


def test_aggregate_metrics_include_mean_stddev_and_sample_count() -> None:
    metrics = average_quality(
        [
            _evaluation(score=3, safety=4, latency_ms=900, cost=0.0010),
            _evaluation(score=5, safety=5, latency_ms=1100, cost=0.0012),
        ]
    )

    assert metrics.sample_count == 2
    assert metrics.quality == 4.0
    assert metrics.quality_stddev > 0
    assert metrics.latency_ms == 1000.0
    assert metrics.latency_ms_stddev == 100.0


def test_tolerance_policy_accepts_small_latency_and_cost_tradeoff() -> None:
    baseline = PromptCandidate(
        version="baseline",
        prompt="base",
        metrics=_metrics(4.0, 4.5, 1000, 0.0010),
    )
    acceptable = PromptCandidate(
        version="acceptable",
        prompt="candidate",
        metrics=_metrics(4.2, 4.5, 1150, 0.00105),
    )
    too_slow = PromptCandidate(
        version="too-slow",
        prompt="candidate",
        metrics=_metrics(4.3, 4.6, 1250, 0.00105),
    )

    selected, decisions = select_candidates_with_policy(
        baseline=baseline,
        candidates=[acceptable, too_slow],
        policy=SelectionPolicy(
            minimum_quality_delta=0.05,
            safety_tolerance=0.0,
            latency_tolerance_ratio=1.20,
            cost_tolerance_ratio=1.10,
        ),
    )

    assert [item.version for item in selected] == ["acceptable"]
    decision_map = {item.version: item for item in decisions}
    assert decision_map["acceptable"].qualifies
    assert not decision_map["too-slow"].qualifies
    assert any("latency" in reason for reason in decision_map["too-slow"].reasons)
