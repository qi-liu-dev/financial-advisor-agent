from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security

from backend.agents import get_agent
from backend.api.converters import run_detail, run_summary
from backend.api.dependencies import (
    audit_repository,
    memory_repository,
    prompt_store,
    trace_logger,
)
from backend.api.errors import llm_http_exception
from backend.audit import AuditRepository
from backend.data_loader import get_task
from backend.evaluation.service import EvaluationService
from backend.llm import LLMError
from backend.memory.advisor_memory import AdvisorMemoryRepository
from backend.models.schemas import (
    AgentRunDetail,
    AgentRunPage,
    AgentType,
    ClientSummaryPayload,
    ClientSummaryOutput,
    DeleteResponse,
    EvaluationResult,
    InvestmentReviewOutput,
    InvestmentReviewPayload,
    MeetingNotesOutput,
    MeetingNotesPayload,
    PurgeRunsResponse,
    RunAgentRequest,
    RunAgentResponse,
    TaskPayload,
    TokenUsage,
    page_metadata,
)
from backend.optimisation.prompt_store import PromptStore
from backend.security.auth import (
    Principal,
    ensure_advisor_access,
    ensure_owner_access,
    get_current_principal,
    require_advisor,
)
from backend.traces.trace_logger import TraceLogger


logger = logging.getLogger("financial_advisor.api.runs")
router = APIRouter(tags=["agent runs"])

_PAYLOAD_MODELS = {
    AgentType.CLIENT_SUMMARY: ClientSummaryPayload,
    AgentType.MEETING_NOTES: MeetingNotesPayload,
    AgentType.INVESTMENT_REVIEW: InvestmentReviewPayload,
}
_OUTPUT_MODELS = {
    AgentType.CLIENT_SUMMARY: ClientSummaryOutput,
    AgentType.MEETING_NOTES: MeetingNotesOutput,
    AgentType.INVESTMENT_REVIEW: InvestmentReviewOutput,
}


@router.post("/run-agent", response_model=RunAgentResponse)
def run_agent(
    body: RunAgentRequest,
    request: Request,
    principal: Principal = Security(require_advisor),
    traces: TraceLogger = Depends(trace_logger),
    prompts: PromptStore = Depends(prompt_store),
    memory: AdvisorMemoryRepository = Depends(memory_repository),
    audit: AuditRepository = Depends(audit_repository),
) -> RunAgentResponse:
    advisor_id = body.advisor_id or principal.principal_id
    ensure_advisor_access(principal, advisor_id)
    payload, task_metadata = _resolve_payload(body)
    preferences = body.preferences or memory.get_preferences(advisor_id)

    try:
        prompt, prompt_version = prompts.get_prompt(
            body.agent_type,
            body.prompt_version,
        )
        agent = get_agent(body.agent_type)
        result = agent.run(
            payload=payload.model_dump(mode="json"),
            preferences=preferences,
            prompt=prompt,
            prompt_version=prompt_version,
        )
    except LLMError as exc:
        raise llm_http_exception(exc) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "prompt_not_found", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception(
            "run_agent_failed agent_type=%s prompt_version=%s",
            body.agent_type.value,
            body.prompt_version or "active",
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "internal_error",
                "message": "The agent run failed unexpectedly.",
            },
        ) from exc

    output = _OUTPUT_MODELS[body.agent_type].model_validate(
        result.output.model_dump(mode="json")
    )
    run_id = str(uuid4())
    full_input = {
        **task_metadata,
        "payload": payload.model_dump(mode="json"),
        "advisor_id": advisor_id,
        "advisor_preferences": preferences.model_dump(mode="json"),
        "repetition_index": None,
    }
    created_at = traces.log_run(
        run_id=run_id,
        owner_id=principal.principal_id,
        advisor_id=advisor_id,
        task_type=body.agent_type.value,
        prompt_version=prompt_version,
        model_name=result.model_name,
        full_input=full_input,
        output=output.model_dump(mode="json"),
        latency_ms=result.latency_ms,
        token_usage=result.token_usage,
        evaluation_scores=None,
        advisor_preferences=preferences.model_dump(mode="json"),
        provider_request_id=result.provider_request_id,
        client_request_id=result.client_request_id,
    )
    audit.log(
        principal_id=principal.principal_id,
        action="create",
        resource_type="agent_run",
        resource_id=run_id,
        request_id=getattr(request.state, "request_id", None),
        metadata={"agent_type": body.agent_type.value, "advisor_id": advisor_id},
    )
    return RunAgentResponse(
        run_id=run_id,
        agent_type=body.agent_type,
        advisor_id=advisor_id,
        prompt_version=prompt_version,
        output=output,
        latency_ms=result.latency_ms,
        token_usage=(
            TokenUsage.model_validate(result.token_usage)
            if result.token_usage is not None
            else None
        ),
        provider_request_id=result.provider_request_id,
        client_request_id=result.client_request_id,
        created_at=created_at,
    )


@router.post("/evaluate-run/{run_id}", response_model=EvaluationResult)
def evaluate_run(
    run_id: str,
    request: Request,
    principal: Principal = Security(get_current_principal),
    traces: TraceLogger = Depends(trace_logger),
    audit: AuditRepository = Depends(audit_repository),
) -> EvaluationResult:
    record = traces.get_run(run_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Run not found."},
        )
    ensure_owner_access(principal, record.owner_id)

    try:
        evaluation = EvaluationService().evaluate(
            agent_type=record.task_type,
            full_input=record.full_input,
            output=record.output,
            latency_ms=record.latency_ms,
            token_usage=record.token_usage,
            agent_model=record.model_name,
        )
    except LLMError as exc:
        raise llm_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("evaluate_run_failed run_id=%s", run_id)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "internal_error",
                "message": "The run evaluation failed unexpectedly.",
            },
        ) from exc

    traces.update_evaluation(run_id, evaluation.model_dump(mode="json"))
    audit.log(
        principal_id=principal.principal_id,
        action="evaluate",
        resource_type="agent_run",
        resource_id=run_id,
        request_id=getattr(request.state, "request_id", None),
    )
    return evaluation


@router.get("/runs", response_model=AgentRunPage)
def runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    agent_type: AgentType | None = None,
    advisor_id: str | None = None,
    owner_id: str | None = None,
    evaluated: bool | None = None,
    principal: Principal = Security(get_current_principal),
    traces: TraceLogger = Depends(trace_logger),
) -> AgentRunPage:
    if not principal.has_role("admin"):
        owner_id = principal.principal_id
        if advisor_id:
            ensure_advisor_access(principal, advisor_id)
    items, total = traces.list_runs_page(
        page=page,
        page_size=page_size,
        owner_id=owner_id,
        advisor_id=advisor_id,
        task_type=agent_type.value if agent_type else None,
        evaluated=evaluated,
    )
    return AgentRunPage(
        items=[run_summary(record) for record in items],
        page=page_metadata(page=page, page_size=page_size, total_items=total),
    )


@router.delete("/runs", response_model=PurgeRunsResponse)
def purge_runs(
    request: Request,
    older_than_days: int = Query(ge=0),
    all_owners: bool = Query(default=False),
    principal: Principal = Security(get_current_principal),
    traces: TraceLogger = Depends(trace_logger),
    audit: AuditRepository = Depends(audit_repository),
) -> PurgeRunsResponse:
    if all_owners and not principal.has_role("admin"):
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Administrator access is required."},
        )
    deleted = traces.purge_runs(
        older_than_days=older_than_days,
        owner_id=None if all_owners else principal.principal_id,
    )
    audit.log(
        principal_id=principal.principal_id,
        action="purge",
        resource_type="agent_run",
        request_id=getattr(request.state, "request_id", None),
        metadata={
            "deleted_count": deleted,
            "older_than_days": older_than_days,
            "all_owners": all_owners,
        },
    )
    return PurgeRunsResponse(
        deleted_count=deleted,
        older_than_days=older_than_days,
    )


@router.get("/runs/{run_id}", response_model=AgentRunDetail)
def get_run_detail(
    run_id: str,
    request: Request,
    principal: Principal = Security(get_current_principal),
    traces: TraceLogger = Depends(trace_logger),
    audit: AuditRepository = Depends(audit_repository),
) -> AgentRunDetail:
    record = traces.get_run(run_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Run not found."},
        )
    ensure_owner_access(principal, record.owner_id)
    audit.log(
        principal_id=principal.principal_id,
        action="read_sensitive",
        resource_type="agent_run",
        resource_id=run_id,
        request_id=getattr(request.state, "request_id", None),
    )
    return run_detail(record)


@router.delete("/runs/{run_id}", response_model=DeleteResponse)
def delete_run(
    run_id: str,
    request: Request,
    principal: Principal = Security(get_current_principal),
    traces: TraceLogger = Depends(trace_logger),
    audit: AuditRepository = Depends(audit_repository),
) -> DeleteResponse:
    record = traces.get_run(run_id)
    if record is None:
        return DeleteResponse(deleted=False, resource_id=run_id)
    ensure_owner_access(principal, record.owner_id)
    deleted = traces.delete_run(run_id)
    audit.log(
        principal_id=principal.principal_id,
        action="delete",
        resource_type="agent_run",
        resource_id=run_id,
        request_id=getattr(request.state, "request_id", None),
        metadata={"deleted": deleted},
    )
    return DeleteResponse(deleted=deleted, resource_id=run_id)


def _resolve_payload(
    body: RunAgentRequest,
) -> tuple[TaskPayload, dict[str, Any]]:
    if body.payload is not None:
        payload = _PAYLOAD_MODELS[body.agent_type].model_validate(
            body.payload.model_dump(mode="json")
        )
        return payload, {
            "task_id": None,
            "difficulty": None,
            "tags": [],
            "expected": None,
        }

    assert body.task_id is not None
    try:
        task = get_task(body.task_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "task_not_found", "message": str(exc)},
        ) from exc
    if task.agent_type != body.agent_type:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "agent_task_mismatch",
                "message": (
                    f"Task {body.task_id} belongs to agent_type={task.agent_type.value}."
                ),
            },
        )
    payload = _PAYLOAD_MODELS[body.agent_type].model_validate(
        task.payload.model_dump(mode="json")
    )
    return payload, {
        "task_id": task.task_id,
        "difficulty": task.difficulty.value,
        "tags": task.tags,
        "expected": task.expected.model_dump(mode="json"),
    }
