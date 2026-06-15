from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query

from backend.agents import get_agent
from backend.data_loader import get_task, list_tasks
from backend.database import init_db
from backend.evaluation.llm_judge import LLMJudgeEvaluator
from backend.evaluation.metrics import combine_evaluations
from backend.evaluation.rule_based import RuleBasedEvaluator
from backend.memory.advisor_memory import AdvisorMemoryRepository
from backend.models.schemas import (
    AgentType,
    MemoryUpdateRequest,
    OptimisationRequest,
    RunAgentRequest,
    RunAgentResponse,
)
from backend.optimisation.gepa_loop import GEPAInspiredOptimiser
from backend.optimisation.prompt_store import PromptStore
from backend.traces.trace_logger import TraceLogger


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    PromptStore().seed_baselines()
    yield


app = FastAPI(
    title="Financial Advisor Agent Optimizer",
    version="0.1.0",
    description=(
        "API-first prototype for evaluating and GEPA-inspired prompt optimisation of "
        "mock financial-advisory LLM agents."
    ),
    lifespan=lifespan,
)

trace_logger = TraceLogger()
prompt_store = PromptStore()
memory_repo = AdvisorMemoryRepository()
rule_evaluator = RuleBasedEvaluator()
judge_evaluator = LLMJudgeEvaluator()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "financial-advisor-agent-optimizer"}


@app.get("/tasks")
def tasks(agent_type: AgentType | None = None) -> list[dict[str, Any]]:
    return list_tasks(agent_type)


@app.post("/run-agent", response_model=RunAgentResponse)
def run_agent(request: RunAgentRequest) -> RunAgentResponse:
    payload = _resolve_payload(request)
    preferences = request.preferences or memory_repo.get_preferences(request.advisor_id)
    try:
        prompt, prompt_version = prompt_store.get_prompt(request.agent_type, request.prompt_version)
        agent = get_agent(request.agent_type)
        result = agent.run(
            payload=payload,
            preferences=preferences,
            prompt=prompt,
            prompt_version=prompt_version,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    run_id = str(uuid4())
    full_input = {
        "task_id": request.task_id,
        "payload": payload,
        "advisor_id": request.advisor_id,
        "advisor_preferences": preferences.model_dump(),
    }
    trace_logger.log_run(
        run_id=run_id,
        task_type=request.agent_type.value,
        prompt_version=prompt_version,
        model_name=result.model_name,
        full_input=full_input,
        output=result.output.model_dump(),
        latency_ms=result.latency_ms,
        token_usage=result.token_usage,
        evaluation_scores=None,
        advisor_preferences=preferences.model_dump(),
    )
    return RunAgentResponse(
        run_id=run_id,
        agent_type=request.agent_type,
        prompt_version=prompt_version,
        output=result.output.model_dump(),
        latency_ms=result.latency_ms,
        token_usage=result.token_usage,
    )


@app.post("/evaluate-run/{run_id}")
def evaluate_run(run_id: str) -> dict[str, Any]:
    record = trace_logger.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    rule_scores = rule_evaluator.evaluate(record.output)
    judge_scores = judge_evaluator.evaluate(
        agent_type=record.task_type,
        full_input=record.full_input,
        output=record.output,
    )
    evaluation = combine_evaluations(
        rule_scores=rule_scores,
        judge_scores=judge_scores,
        latency_ms=record.latency_ms,
        token_usage=record.token_usage,
    )
    trace_logger.update_evaluation(run_id, evaluation.model_dump())
    return evaluation.model_dump()


@app.post("/optimise/{agent_type}")
def optimise(agent_type: AgentType, request: OptimisationRequest) -> dict[str, Any]:
    try:
        return GEPAInspiredOptimiser().optimise(
            agent_type=agent_type,
            advisor_id=request.advisor_id,
            max_variants=request.max_variants,
            benchmark_limit=request.benchmark_limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/runs")
def runs(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return [_record_to_dict(record) for record in trace_logger.list_runs(limit=limit)]


@app.get("/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    record = trace_logger.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return _record_to_dict(record)


@app.get("/prompt-versions/{agent_type}")
def prompt_versions(agent_type: AgentType) -> list[dict[str, Any]]:
    return prompt_store.list_prompt_versions(agent_type)


@app.post("/memory/{advisor_id}")
def update_memory(advisor_id: str, request: MemoryUpdateRequest) -> dict[str, Any]:
    preferences = memory_repo.save_preferences(advisor_id, request.preferences)
    return {"advisor_id": advisor_id, "preferences": preferences.model_dump()}


def _resolve_payload(request: RunAgentRequest) -> dict[str, Any]:
    if request.payload is not None:
        return request.payload
    if not request.task_id:
        raise HTTPException(status_code=400, detail="Either payload or task_id is required.")
    try:
        task = get_task(request.task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if task["agent_type"] != request.agent_type.value:
        raise HTTPException(
            status_code=400,
            detail=f"Task {request.task_id} belongs to agent_type={task['agent_type']}.",
        )
    return task["payload"]


def _record_to_dict(record: Any) -> dict[str, Any]:
    return {
        "run_id": record.run_id,
        "task_type": record.task_type,
        "prompt_version": record.prompt_version,
        "model_name": record.model_name,
        "input_hash": record.input_hash,
        "full_input": record.full_input,
        "output": record.output,
        "latency_ms": record.latency_ms,
        "token_usage": record.token_usage,
        "evaluation_scores": record.evaluation_scores,
        "advisor_preferences": record.advisor_preferences,
        "timestamp": record.timestamp.isoformat(),
    }
