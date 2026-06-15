from __future__ import annotations

from backend.data_loader import list_tasks
from backend.evaluation.regression import check_thresholds, load_thresholds
from backend.models.schemas import AgentType, EvaluationResult, MetricScore


def _score(value: int) -> MetricScore:
    return MetricScore(score=value, feedback="test")


def _evaluation(
    *,
    score: int = 5,
    safety: int = 5,
    latency_ms: float = 1000.0,
    estimated_cost: float = 0.0001,
    benchmark_score: int = 5,
) -> EvaluationResult:
    return EvaluationResult(
        faithfulness=_score(score),
        completeness=_score(score),
        risk_awareness=_score(score),
        clarity=_score(score),
        advisor_usefulness=_score(score),
        safety=_score(safety),
        format_correctness=_score(score),
        benchmark_expectations=_score(benchmark_score),
        latency_ms=latency_ms,
        estimated_cost=estimated_cost,
        feedback="test",
    )


def test_threshold_check_passes_for_good_metrics() -> None:
    result = check_thresholds(
        agent_type=AgentType.CLIENT_SUMMARY,
        evaluations=[_evaluation()],
        thresholds_by_agent={
            "client_summary": {
                "min_quality": 4.2,
                "min_safety": 5.0,
                "min_format_correctness": 5.0,
                "min_benchmark_expectations": 4.0,
                "max_latency_ms": 15000,
                "max_estimated_cost": 0.002,
            }
        },
    )

    assert result.passed
    assert result.failures == []


def test_threshold_check_fails_for_safety_and_latency_regression() -> None:
    result = check_thresholds(
        agent_type=AgentType.CLIENT_SUMMARY,
        evaluations=[_evaluation(safety=4, latency_ms=20000)],
        thresholds_by_agent={
            "client_summary": {
                "min_quality": 4.0,
                "min_safety": 5.0,
                "max_latency_ms": 15000,
            }
        },
    )

    assert not result.passed
    assert any("safety" in failure for failure in result.failures)
    assert any("latency_ms" in failure for failure in result.failures)


def test_benchmark_tasks_include_richer_metadata_and_expected_checks() -> None:
    tasks = list_tasks(AgentType.CLIENT_SUMMARY)

    assert len(tasks) >= 3
    assert all("difficulty" in task for task in tasks)
    assert all("tags" in task for task in tasks)
    assert all("expected" in task for task in tasks)


def test_regression_threshold_config_covers_all_agents() -> None:
    thresholds = load_thresholds()

    assert set(thresholds) == {agent_type.value for agent_type in AgentType}
    assert thresholds["investment_review"]["min_risk_awareness"] >= 4.0
