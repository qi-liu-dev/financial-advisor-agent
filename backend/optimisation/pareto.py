from __future__ import annotations

from dataclasses import dataclass


MAXIMISE = ("quality", "safety")
MINIMISE = ("latency_ms", "estimated_cost")


@dataclass(frozen=True)
class PromptCandidate:
    version: str
    prompt: str
    metrics: dict[str, float]


def dominates(candidate: PromptCandidate, other: PromptCandidate) -> bool:
    no_worse = all(candidate.metrics[key] >= other.metrics[key] for key in MAXIMISE)
    no_worse = no_worse and all(candidate.metrics[key] <= other.metrics[key] for key in MINIMISE)
    strictly_better = any(candidate.metrics[key] > other.metrics[key] for key in MAXIMISE)
    strictly_better = strictly_better or any(candidate.metrics[key] < other.metrics[key] for key in MINIMISE)
    return no_worse and strictly_better


def pareto_improving_candidates(
    baseline: PromptCandidate,
    candidates: list[PromptCandidate],
) -> list[PromptCandidate]:
    improving = [candidate for candidate in candidates if dominates(candidate, baseline)]
    frontier = [
        candidate
        for candidate in improving
        if not any(dominates(other, candidate) for other in improving if other != candidate)
    ]
    return sorted(
        frontier,
        key=lambda item: (
            item.metrics["quality"],
            item.metrics["safety"],
            -item.metrics["estimated_cost"],
            -item.metrics["latency_ms"],
        ),
        reverse=True,
    )
