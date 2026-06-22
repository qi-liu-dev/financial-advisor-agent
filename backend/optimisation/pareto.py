from __future__ import annotations

from dataclasses import dataclass

from backend.models.schemas import OptimisationMetrics


MAXIMISE = ("quality", "safety")
MINIMISE = ("latency_ms", "estimated_cost")


@dataclass(frozen=True)
class PromptCandidate:
    version: str
    prompt: str
    metrics: OptimisationMetrics | dict[str, float]


@dataclass(frozen=True)
class SelectionPolicy:
    minimum_quality_delta: float = 0.05
    safety_tolerance: float = 0.0
    latency_tolerance_ratio: float = 1.20
    cost_tolerance_ratio: float = 1.10


@dataclass(frozen=True)
class CandidateDecision:
    version: str
    qualifies: bool
    selected: bool
    reasons: tuple[str, ...]


def dominates(candidate: PromptCandidate, other: PromptCandidate) -> bool:
    no_worse = all(_metric(candidate, key) >= _metric(other, key) for key in MAXIMISE)
    no_worse = no_worse and all(
        _metric(candidate, key) <= _metric(other, key) for key in MINIMISE
    )
    strictly_better = any(
        _metric(candidate, key) > _metric(other, key) for key in MAXIMISE
    )
    strictly_better = strictly_better or any(
        _metric(candidate, key) < _metric(other, key) for key in MINIMISE
    )
    return no_worse and strictly_better


def pareto_improving_candidates(
    baseline: PromptCandidate,
    candidates: list[PromptCandidate],
) -> list[PromptCandidate]:
    """Legacy strict-Pareto selector retained for regression compatibility."""

    improving = [candidate for candidate in candidates if dominates(candidate, baseline)]
    return _frontier(improving)


def select_candidates_with_policy(
    *,
    baseline: PromptCandidate,
    candidates: list[PromptCandidate],
    policy: SelectionPolicy,
) -> tuple[list[PromptCandidate], list[CandidateDecision]]:
    qualified: list[PromptCandidate] = []
    reasons_by_version: dict[str, tuple[str, ...]] = {}

    for candidate in candidates:
        reasons: list[str] = []
        quality_delta = _metric(candidate, "quality") - _metric(baseline, "quality")
        if quality_delta < policy.minimum_quality_delta:
            reasons.append(
                f"quality delta {quality_delta:.3f} is below required "
                f"{policy.minimum_quality_delta:.3f}"
            )
        if (
            _metric(candidate, "safety") + policy.safety_tolerance
            < _metric(baseline, "safety")
        ):
            reasons.append("safety is below the baseline tolerance")
        if _metric(candidate, "latency_ms") > (
            _metric(baseline, "latency_ms") * policy.latency_tolerance_ratio
        ):
            reasons.append(
                "mean latency exceeds the configured baseline multiplier"
            )
        if _metric(candidate, "estimated_cost") > (
            _metric(baseline, "estimated_cost") * policy.cost_tolerance_ratio
        ):
            reasons.append("mean estimated cost exceeds the configured baseline multiplier")

        if not reasons:
            qualified.append(candidate)
            reasons.append("passes quality, safety, latency, and cost guardrails")
        reasons_by_version[candidate.version] = tuple(reasons)

    selected = _frontier(qualified)
    selected_versions = {candidate.version for candidate in selected}
    decisions = [
        CandidateDecision(
            version=candidate.version,
            qualifies=candidate in qualified,
            selected=candidate.version in selected_versions,
            reasons=reasons_by_version[candidate.version]
            + (
                ("lies on the Pareto frontier of qualified candidates",)
                if candidate.version in selected_versions
                else (
                    ("dominated by another qualified candidate",)
                    if candidate in qualified
                    else ()
                )
            ),
        )
        for candidate in candidates
    ]
    return selected, decisions


def _frontier(candidates: list[PromptCandidate]) -> list[PromptCandidate]:
    frontier = [
        candidate
        for candidate in candidates
        if not any(
            dominates(other, candidate)
            for other in candidates
            if other.version != candidate.version
        )
    ]
    return sorted(
        frontier,
        key=lambda item: (
            _metric(item, "quality"),
            _metric(item, "safety"),
            -_metric(item, "estimated_cost"),
            -_metric(item, "latency_ms"),
        ),
        reverse=True,
    )


def _metric(candidate: PromptCandidate, key: str) -> float:
    if isinstance(candidate.metrics, OptimisationMetrics):
        return float(getattr(candidate.metrics, key))
    return float(candidate.metrics[key])
