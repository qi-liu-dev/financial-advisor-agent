from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.agents import get_agent
from backend.config import get_settings
from backend.data_loader import list_tasks
from backend.evaluation.metrics import average_quality, evaluation_quality_score
from backend.evaluation.service import EvaluationService
from backend.memory.advisor_memory import AdvisorMemoryRepository
from backend.models.schemas import (
    AgentType,
    BenchmarkTaskResponse,
    EvaluationResult,
    OptimisationBaselineResponse,
    OptimisationCandidateResponse,
    OptimisationResultResponse,
    OptimisationSelectionPolicy,
    PromptStatus,
)
from backend.optimisation.pareto import (
    PromptCandidate,
    SelectionPolicy,
    select_candidates_with_policy,
)
from backend.optimisation.prompt_mutation import PromptMutator
from backend.optimisation.prompt_store import PromptStore
from backend.optimisation.reflection import ReflectionGenerator
from backend.traces.trace_logger import TraceLogger


class GEPAInspiredOptimiser:
    def __init__(self) -> None:
        self.prompt_store = PromptStore()
        self.trace_logger = TraceLogger()
        self.evaluation_service = EvaluationService()
        self.memory = AdvisorMemoryRepository()
        self.reflection_generator = ReflectionGenerator()
        self.prompt_mutator = PromptMutator()

    def optimise(
        self,
        *,
        agent_type: AgentType,
        advisor_id: str,
        owner_id: str = "demo-advisor",
        job_id: str | None = None,
        max_variants: int,
        benchmark_limit: int | None,
        repetitions: int | None = None,
        progress_callback: Callable[[float], None] | None = None,
    ) -> OptimisationResultResponse:
        settings = get_settings()
        repetitions = repetitions or settings.optimisation_default_repetitions
        if repetitions > settings.optimisation_max_repetitions:
            raise ValueError(
                f"repetitions cannot exceed {settings.optimisation_max_repetitions}."
            )

        self.prompt_store.seed_baselines()
        tasks = list_tasks(agent_type)
        if benchmark_limit:
            tasks = tasks[:benchmark_limit]
        if not tasks:
            raise ValueError(f"No benchmark tasks found for {agent_type.value}.")

        _progress(progress_callback, 0.03)
        baseline_prompt, baseline_version = self.prompt_store.get_prompt(agent_type)
        baseline_evaluations = self._run_benchmark(
            agent_type=agent_type,
            prompt=baseline_prompt,
            prompt_version=baseline_version,
            advisor_id=advisor_id,
            owner_id=owner_id,
            tasks=tasks,
            repetitions=repetitions,
        )
        baseline_metrics = average_quality(
            [item["evaluation"] for item in baseline_evaluations]
        )
        baseline_candidate = PromptCandidate(
            version=baseline_version,
            prompt=baseline_prompt,
            metrics=baseline_metrics,
        )
        _progress(progress_callback, 0.30)

        weak_cases = [
            self._weak_case_summary(item)
            for item in baseline_evaluations
            if item["average_score"] < 4.0 or item["evaluation"].safety.score < 4
        ]
        reflection = self.reflection_generator.generate(
            agent_type=agent_type.value,
            weak_cases=weak_cases
            or [self._weak_case_summary(item) for item in baseline_evaluations],
        )
        generated_variants = self.prompt_mutator.generate(
            baseline_prompt=baseline_prompt,
            reflection=reflection,
            max_variants=max_variants,
        )
        _progress(progress_callback, 0.38)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        candidates: list[PromptCandidate] = []
        raw_candidate_results: list[dict[str, Any]] = []
        for index, variant in enumerate(generated_variants, start=1):
            version = f"gepa_inspired_{timestamp}_{index}"
            evaluations = self._run_benchmark(
                agent_type=agent_type,
                prompt=variant.prompt,
                prompt_version=version,
                advisor_id=advisor_id,
                owner_id=owner_id,
                tasks=tasks,
                repetitions=repetitions,
            )
            metrics = average_quality([item["evaluation"] for item in evaluations])
            candidate = PromptCandidate(
                version=version,
                prompt=variant.prompt,
                metrics=metrics,
            )
            candidates.append(candidate)
            raw_candidate_results.append(
                {
                    "version": version,
                    "rationale": variant.rationale,
                    "metrics": metrics,
                    "run_ids": [item["run_id"] for item in evaluations],
                }
            )
            self.prompt_store.save_prompt_version(
                agent_type=agent_type,
                version=version,
                prompt=variant.prompt,
                parent_version=baseline_version,
                reflection=reflection,
                average_scores=metrics,
                status=PromptStatus.CANDIDATE,
            )
            _progress(
                progress_callback,
                0.38 + (0.50 * index / max(1, len(generated_variants))),
            )

        selection_policy = SelectionPolicy(
            minimum_quality_delta=settings.optimisation_minimum_quality_delta,
            safety_tolerance=settings.optimisation_safety_tolerance,
            latency_tolerance_ratio=settings.optimisation_latency_tolerance_ratio,
            cost_tolerance_ratio=settings.optimisation_cost_tolerance_ratio,
        )
        selected, decisions = select_candidates_with_policy(
            baseline=baseline_candidate,
            candidates=candidates,
            policy=selection_policy,
        )
        selected_versions = [candidate.version for candidate in selected]
        candidate_versions = [candidate.version for candidate in candidates]
        self.prompt_store.mark_candidate_selection(
            agent_type=agent_type,
            candidate_versions=candidate_versions,
            selected_versions=selected_versions,
        )
        decision_map = {decision.version: decision for decision in decisions}
        candidate_responses = [
            OptimisationCandidateResponse(
                version=item["version"],
                rationale=item["rationale"],
                metrics=item["metrics"],
                run_ids=item["run_ids"],
                status=(
                    PromptStatus.SELECTED
                    if item["version"] in selected_versions
                    else PromptStatus.REJECTED
                ),
                qualifies=decision_map[item["version"]].qualifies,
                selected=decision_map[item["version"]].selected,
                reasons=list(decision_map[item["version"]].reasons),
            )
            for item in raw_candidate_results
        ]

        policy_response = OptimisationSelectionPolicy(
            minimum_quality_delta=selection_policy.minimum_quality_delta,
            safety_tolerance=selection_policy.safety_tolerance,
            latency_tolerance_ratio=selection_policy.latency_tolerance_ratio,
            cost_tolerance_ratio=selection_policy.cost_tolerance_ratio,
        )
        baseline_response = OptimisationBaselineResponse(
            version=baseline_version,
            metrics=baseline_metrics,
            run_ids=[item["run_id"] for item in baseline_evaluations],
        )
        comparison = {
            "baseline": baseline_response.model_dump(mode="json"),
            "reflection": reflection,
            "candidates": [
                candidate.model_dump(mode="json") for candidate in candidate_responses
            ],
            "selected_versions": selected_versions,
            "selection_policy": policy_response.model_dump(mode="json"),
            "selection_note": (
                "Candidates first pass mean-quality, safety, latency, and cost guardrails; "
                "the Pareto frontier is then selected. Selected prompts are not activated "
                "automatically and require an explicit activation API call."
            ),
        }
        optimisation_id, created_at = self.prompt_store.save_optimisation_result(
            owner_id=owner_id,
            job_id=job_id,
            agent_type=agent_type,
            baseline_version=baseline_version,
            selected_versions=selected_versions,
            comparison_results=comparison,
        )
        _progress(progress_callback, 0.98)
        return OptimisationResultResponse(
            optimisation_id=optimisation_id,
            job_id=job_id,
            owner_id=owner_id,
            agent_type=agent_type,
            baseline=baseline_response,
            reflection=reflection,
            candidates=candidate_responses,
            selected_versions=selected_versions,
            selection_policy=policy_response,
            selection_note=comparison["selection_note"],
            created_at=created_at,
        )

    def _run_benchmark(
        self,
        *,
        agent_type: AgentType,
        prompt: str,
        prompt_version: str,
        advisor_id: str,
        owner_id: str,
        tasks: list[BenchmarkTaskResponse],
        repetitions: int = 1,
    ) -> list[dict[str, Any]]:
        agent = get_agent(agent_type)
        preferences = self.memory.get_preferences(advisor_id)
        results: list[dict[str, Any]] = []
        for task in tasks:
            for repetition_index in range(1, repetitions + 1):
                run_id = str(uuid4())
                full_input = {
                    "task_id": task.task_id,
                    "difficulty": task.difficulty.value,
                    "tags": task.tags,
                    "expected": task.expected.model_dump(mode="json"),
                    "payload": task.payload.model_dump(mode="json"),
                    "advisor_id": advisor_id,
                    "advisor_preferences": preferences.model_dump(mode="json"),
                    "repetition_index": repetition_index,
                }
                agent_result = agent.run(
                    payload=task.payload.model_dump(mode="json"),
                    preferences=preferences,
                    prompt=prompt,
                    prompt_version=prompt_version,
                )
                self.trace_logger.log_run(
                    run_id=run_id,
                    owner_id=owner_id,
                    advisor_id=advisor_id,
                    task_type=agent_type.value,
                    prompt_version=prompt_version,
                    model_name=agent_result.model_name,
                    full_input=full_input,
                    output=agent_result.output.model_dump(mode="json"),
                    latency_ms=agent_result.latency_ms,
                    token_usage=agent_result.token_usage,
                    evaluation_scores=None,
                    advisor_preferences=preferences.model_dump(mode="json"),
                    provider_request_id=agent_result.provider_request_id,
                    client_request_id=agent_result.client_request_id,
                )
                evaluation = self.evaluation_service.evaluate(
                    agent_type=agent_type.value,
                    full_input=full_input,
                    output=agent_result.output.model_dump(mode="json"),
                    latency_ms=agent_result.latency_ms,
                    token_usage=agent_result.token_usage,
                    agent_model=agent_result.model_name,
                    expected=task.expected,
                )
                self.trace_logger.update_evaluation(
                    run_id,
                    evaluation.model_dump(mode="json"),
                )
                results.append(
                    {
                        "run_id": run_id,
                        "task_id": task.task_id,
                        "repetition_index": repetition_index,
                        "evaluation": evaluation,
                        "average_score": evaluation_quality_score(evaluation),
                    }
                )
        return results

    def _weak_case_summary(self, item: dict[str, Any]) -> dict[str, Any]:
        evaluation: EvaluationResult = item["evaluation"]
        return {
            "run_id": item["run_id"],
            "task_id": item["task_id"],
            "repetition_index": item.get("repetition_index"),
            "average_score": item["average_score"],
            "scores": {
                "faithfulness": evaluation.faithfulness.score,
                "completeness": evaluation.completeness.score,
                "risk_awareness": evaluation.risk_awareness.score,
                "clarity": evaluation.clarity.score,
                "advisor_usefulness": evaluation.advisor_usefulness.score,
                "safety": evaluation.safety.score,
                "format_correctness": evaluation.format_correctness.score,
                "benchmark_expectations": (
                    evaluation.benchmark_expectations.score
                    if evaluation.benchmark_expectations
                    else None
                ),
            },
            "feedback": evaluation.feedback,
        }


def _progress(callback: Callable[[float], None] | None, value: float) -> None:
    if callback:
        callback(min(1.0, max(0.0, value)))
