from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any

from backend.config import DATA_DIR
from backend.data_loader import list_tasks, load_json_file
from backend.evaluation.metrics import average_quality
from backend.models.schemas import AgentType, EvaluationResult
from backend.optimisation.gepa_loop import GEPAInspiredOptimiser


@dataclass(frozen=True)
class RegressionCheckResult:
    passed: bool
    failures: list[str]
    metrics: dict[str, float]
    thresholds: dict[str, float]
    run_ids: list[str]


def load_thresholds() -> dict[str, dict[str, float]]:
    return load_json_file(DATA_DIR / "regression_thresholds.json")


def check_thresholds(
    *,
    agent_type: AgentType,
    evaluations: list[EvaluationResult],
    thresholds_by_agent: dict[str, dict[str, float]] | None = None,
) -> RegressionCheckResult:
    thresholds_by_agent = thresholds_by_agent or load_thresholds()
    thresholds = thresholds_by_agent[agent_type.value]
    metrics = _aggregate_regression_metrics(evaluations)
    failures = _compare_metrics(metrics=metrics, thresholds=thresholds)
    return RegressionCheckResult(
        passed=not failures,
        failures=failures,
        metrics=metrics,
        thresholds=thresholds,
        run_ids=[],
    )


def run_regression_suite(
    *,
    agent_type: AgentType,
    advisor_id: str = "demo-advisor",
    benchmark_limit: int | None = None,
    prompt_version: str | None = "baseline",
    repetitions: int = 1,
) -> RegressionCheckResult:
    optimiser = GEPAInspiredOptimiser()
    optimiser.prompt_store.seed_baselines()
    prompt, resolved_version = optimiser.prompt_store.get_prompt(
        agent_type,
        prompt_version,
    )
    tasks = list_tasks(agent_type)
    if benchmark_limit:
        tasks = tasks[:benchmark_limit]
    results = optimiser._run_benchmark(
        agent_type=agent_type,
        prompt=prompt,
        prompt_version=resolved_version,
        advisor_id=advisor_id,
        owner_id=advisor_id,
        tasks=tasks,
        repetitions=repetitions,
    )
    threshold_result = check_thresholds(
        agent_type=agent_type,
        evaluations=[item["evaluation"] for item in results],
    )
    return RegressionCheckResult(
        passed=threshold_result.passed,
        failures=threshold_result.failures,
        metrics=threshold_result.metrics,
        thresholds=threshold_result.thresholds,
        run_ids=[item["run_id"] for item in results],
    )


def _aggregate_regression_metrics(
    evaluations: list[EvaluationResult],
) -> dict[str, float]:
    aggregate = average_quality(evaluations).model_dump()
    if not evaluations:
        return {
            **aggregate,
            "format_correctness": 0.0,
            "risk_awareness": 0.0,
            "benchmark_expectations": 0.0,
        }
    aggregate.update(
        {
            "format_correctness": round(
                sum(item.format_correctness.score for item in evaluations)
                / len(evaluations),
                3,
            ),
            "risk_awareness": round(
                sum(item.risk_awareness.score for item in evaluations)
                / len(evaluations),
                3,
            ),
            "benchmark_expectations": round(
                sum(
                    item.benchmark_expectations.score
                    for item in evaluations
                    if item.benchmark_expectations is not None
                )
                / max(
                    1,
                    sum(
                        1
                        for item in evaluations
                        if item.benchmark_expectations is not None
                    ),
                ),
                3,
            ),
        }
    )
    return {key: float(value) for key, value in aggregate.items()}


def _compare_metrics(
    *,
    metrics: dict[str, float],
    thresholds: dict[str, float],
) -> list[str]:
    failures: list[str] = []
    threshold_to_metric = {
        "min_quality": "quality",
        "min_safety": "safety",
        "min_format_correctness": "format_correctness",
        "min_risk_awareness": "risk_awareness",
        "min_benchmark_expectations": "benchmark_expectations",
    }
    for threshold_name, metric_name in threshold_to_metric.items():
        if (
            threshold_name in thresholds
            and metrics[metric_name] < thresholds[threshold_name]
        ):
            failures.append(
                f"{metric_name}={metrics[metric_name]} is below "
                f"{threshold_name}={thresholds[threshold_name]}"
            )
    for threshold_name, metric_name in {
        "max_latency_ms": "latency_ms",
        "max_estimated_cost": "estimated_cost",
    }.items():
        if (
            threshold_name in thresholds
            and metrics[metric_name] > thresholds[threshold_name]
        ):
            failures.append(
                f"{metric_name}={metrics[metric_name]} is above "
                f"{threshold_name}={thresholds[threshold_name]}"
            )
    return failures


def _result_to_dict(result: RegressionCheckResult) -> dict[str, Any]:
    return {
        "passed": result.passed,
        "failures": result.failures,
        "metrics": result.metrics,
        "thresholds": result.thresholds,
        "run_ids": result.run_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run benchmark regression checks for one agent."
    )
    parser.add_argument(
        "--agent",
        choices=[item.value for item in AgentType],
        required=True,
    )
    parser.add_argument("--advisor-id", default="demo-advisor")
    parser.add_argument("--benchmark-limit", type=int, default=None)
    parser.add_argument("--prompt-version", default="baseline")
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()

    result = run_regression_suite(
        agent_type=AgentType(args.agent),
        advisor_id=args.advisor_id,
        benchmark_limit=args.benchmark_limit,
        prompt_version=args.prompt_version,
        repetitions=args.repetitions,
    )
    print(json.dumps(_result_to_dict(result), indent=2, sort_keys=True))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
