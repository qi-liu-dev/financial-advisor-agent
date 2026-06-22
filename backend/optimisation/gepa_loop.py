from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.agents import get_agent
from backend.data_loader import list_tasks
from backend.evaluation.benchmark_expectations import BenchmarkExpectationEvaluator
from backend.evaluation.llm_judge import LLMJudgeEvaluator
from backend.evaluation.metrics import average_quality, combine_evaluations
from backend.evaluation.rule_based import RuleBasedEvaluator
from backend.memory.advisor_memory import AdvisorMemoryRepository
from backend.models.schemas import AgentType, EvaluationResult
from backend.optimisation.pareto import PromptCandidate, pareto_improving_candidates
from backend.optimisation.prompt_mutation import PromptMutator
from backend.optimisation.prompt_store import PromptStore
from backend.optimisation.reflection import ReflectionGenerator
from backend.traces.trace_logger import TraceLogger


class GEPAInspiredOptimiser:
    def __init__(self) -> None:
        self.prompt_store = PromptStore()
        self.trace_logger = TraceLogger()
        self.rule_evaluator = RuleBasedEvaluator()
        self.expectation_evaluator = BenchmarkExpectationEvaluator()
        self.judge = LLMJudgeEvaluator()
        self.memory = AdvisorMemoryRepository()
        self.reflection_generator = ReflectionGenerator()
        self.prompt_mutator = PromptMutator()

    def optimise(
        self,
        *,
        agent_type: AgentType,
        advisor_id: str,
        max_variants: int,
        benchmark_limit: int | None,
    ) -> dict[str, Any]:
        self.prompt_store.seed_baselines()
        tasks = list_tasks(agent_type)
        if benchmark_limit:
            tasks = tasks[:benchmark_limit]
        if not tasks:
            raise ValueError(f"No benchmark tasks found for {agent_type.value}.")

        baseline_prompt, baseline_version = self.prompt_store.get_prompt(agent_type, "baseline")
        baseline_evaluations = self._run_benchmark(
            agent_type=agent_type,
            prompt=baseline_prompt,
            prompt_version=baseline_version,
            advisor_id=advisor_id,
            tasks=tasks,
        )
        baseline_metrics = average_quality([item["evaluation"] for item in baseline_evaluations])
        baseline_candidate = PromptCandidate(
            version=baseline_version,
            prompt=baseline_prompt,
            metrics=baseline_metrics,
        )

        weak_cases = [
            self._weak_case_summary(item)
            for item in baseline_evaluations
            if item["average_score"] < 4.0 or item["evaluation"].safety.score < 4
        ]
        reflection = self.reflection_generator.generate(
            agent_type=agent_type.value,
            weak_cases=weak_cases or [self._weak_case_summary(item) for item in baseline_evaluations],
        )

        generated_variants = self.prompt_mutator.generate(
            baseline_prompt=baseline_prompt,
            reflection=reflection,
            max_variants=max_variants,
        )

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        candidates: list[PromptCandidate] = []
        candidate_results: list[dict[str, Any]] = []
        for index, variant in enumerate(generated_variants, start=1):
            version = f"gepa_inspired_{timestamp}_{index}"
            evaluations = self._run_benchmark(
                agent_type=agent_type,
                prompt=variant.prompt,
                prompt_version=version,
                advisor_id=advisor_id,
                tasks=tasks,
            )
            metrics = average_quality([item["evaluation"] for item in evaluations])
            candidate = PromptCandidate(version=version, prompt=variant.prompt, metrics=metrics)
            candidates.append(candidate)
            candidate_results.append(
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
            )

        selected = pareto_improving_candidates(baseline_candidate, candidates)
        selected_versions = [candidate.version for candidate in selected]
        comparison = {
            "baseline": {
                "version": baseline_version,
                "metrics": baseline_metrics,
                "run_ids": [item["run_id"] for item in baseline_evaluations],
            },
            "reflection": reflection,
            "candidates": candidate_results,
            "selected_versions": selected_versions,
            "selection_note": "Selected candidates strictly dominate the baseline on quality/safety/cost/latency trade-offs.",
        }
        optimisation_id = self.prompt_store.save_optimisation_result(
            agent_type=agent_type,
            baseline_version=baseline_version,
            selected_versions=selected_versions,
            comparison_results=comparison,
        )
        return {"optimisation_id": optimisation_id, **comparison}

    def _run_benchmark(
        self,
        *,
        agent_type: AgentType,
        prompt: str,
        prompt_version: str,
        advisor_id: str,
        tasks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        agent = get_agent(agent_type)
        preferences = self.memory.get_preferences(advisor_id)
        results: list[dict[str, Any]] = []
        for task in tasks:
            run_id = str(uuid4())
            full_input = {
                "task_id": task["task_id"],
                "difficulty": task.get("difficulty"),
                "tags": task.get("tags", []),
                "expected": task.get("expected"),
                "payload": task["payload"],
                "advisor_id": advisor_id,
                "advisor_preferences": preferences.model_dump(),
            }
            agent_result = agent.run(
                payload=task["payload"],
                preferences=preferences,
                prompt=prompt,
                prompt_version=prompt_version,
            )
            self.trace_logger.log_run(
                run_id=run_id,
                task_type=agent_type.value,
                prompt_version=prompt_version,
                model_name=agent_result.model_name,
                full_input=full_input,
                output=agent_result.output.model_dump(),
                latency_ms=agent_result.latency_ms,
                token_usage=agent_result.token_usage,
                evaluation_scores=None,
                advisor_preferences=preferences.model_dump(),
                provider_request_id=agent_result.provider_request_id,
                client_request_id=agent_result.client_request_id,
            )
            rule_scores = self.rule_evaluator.evaluate(agent_result.output.model_dump())
            expectation_score = self.expectation_evaluator.evaluate(
                agent_result.output.model_dump(),
                task.get("expected"),
            )
            judge_scores = self.judge.evaluate(
                agent_type=agent_type.value,
                full_input=full_input,
                output=agent_result.output.model_dump(),
            )
            evaluation = combine_evaluations(
                rule_scores=rule_scores,
                judge_scores=judge_scores,
                latency_ms=agent_result.latency_ms,
                token_usage=agent_result.token_usage,
                benchmark_expectations=expectation_score,
            )
            self.trace_logger.update_evaluation(run_id, evaluation.model_dump())
            results.append(
                {
                    "run_id": run_id,
                    "task_id": task["task_id"],
                    "evaluation": evaluation,
                    "average_score": self._average_score(evaluation),
                }
            )
        return results

    def _average_score(self, evaluation: EvaluationResult) -> float:
        fields = [
            evaluation.faithfulness,
            evaluation.completeness,
            evaluation.risk_awareness,
            evaluation.clarity,
            evaluation.advisor_usefulness,
            evaluation.safety,
            evaluation.format_correctness,
        ]
        return sum(field.score for field in fields) / len(fields)

    def _weak_case_summary(self, item: dict[str, Any]) -> dict[str, Any]:
        evaluation: EvaluationResult = item["evaluation"]
        return {
            "run_id": item["run_id"],
            "task_id": item["task_id"],
            "average_score": item["average_score"],
            "scores": {
                "faithfulness": evaluation.faithfulness.score,
                "completeness": evaluation.completeness.score,
                "risk_awareness": evaluation.risk_awareness.score,
                "clarity": evaluation.clarity.score,
                "advisor_usefulness": evaluation.advisor_usefulness.score,
                "safety": evaluation.safety.score,
                "format_correctness": evaluation.format_correctness.score,
            },
            "feedback": evaluation.feedback,
        }
