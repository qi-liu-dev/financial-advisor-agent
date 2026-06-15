from __future__ import annotations

from backend.optimisation.pareto import PromptCandidate, dominates, pareto_improving_candidates


def test_candidate_dominates_when_quality_safety_improve_and_cost_latency_do_not() -> None:
    baseline = PromptCandidate(
        version="baseline",
        prompt="baseline",
        metrics={"quality": 3.8, "safety": 4.0, "latency_ms": 900.0, "estimated_cost": 0.001},
    )
    candidate = PromptCandidate(
        version="variant",
        prompt="variant",
        metrics={"quality": 4.2, "safety": 4.2, "latency_ms": 850.0, "estimated_cost": 0.0009},
    )

    assert dominates(candidate, baseline)


def test_pareto_selection_filters_non_improving_variants() -> None:
    baseline = PromptCandidate(
        version="baseline",
        prompt="baseline",
        metrics={"quality": 4.0, "safety": 4.0, "latency_ms": 1000.0, "estimated_cost": 0.002},
    )
    better = PromptCandidate(
        version="better",
        prompt="better",
        metrics={"quality": 4.4, "safety": 4.1, "latency_ms": 900.0, "estimated_cost": 0.0018},
    )
    slower = PromptCandidate(
        version="slower",
        prompt="slower",
        metrics={"quality": 4.5, "safety": 4.2, "latency_ms": 1200.0, "estimated_cost": 0.0018},
    )

    selected = pareto_improving_candidates(baseline, [better, slower])

    assert [candidate.version for candidate in selected] == ["better"]
