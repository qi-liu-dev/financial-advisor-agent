from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security, status

from backend.api.dependencies import (
    audit_repository,
    optimisation_job_manager,
    optimisation_job_store,
    prompt_store,
)
from backend.audit import AuditRepository
from backend.models.schemas import (
    AgentType,
    OptimisationJobPage,
    OptimisationJobResponse,
    OptimisationJobStatus,
    OptimisationRequest,
    OptimisationResultPage,
    OptimisationResultResponse,
    page_metadata,
)
from backend.optimisation.jobs import (
    OptimisationJobConflict,
    OptimisationJobManager,
    OptimisationJobStore,
)
from backend.optimisation.prompt_store import PromptStore
from backend.security.auth import (
    Principal,
    ensure_advisor_access,
    ensure_owner_access,
    get_current_principal,
    require_advisor,
)


router = APIRouter(tags=["optimisation"])


@router.post(
    "/optimisations/{agent_type}",
    response_model=OptimisationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_optimisation(
    agent_type: AgentType,
    body: OptimisationRequest,
    request: Request,
    principal: Principal = Security(require_advisor),
    manager: OptimisationJobManager = Depends(optimisation_job_manager),
    audit: AuditRepository = Depends(audit_repository),
) -> OptimisationJobResponse:
    settings = request.app.state.settings
    advisor_id = body.advisor_id or principal.principal_id
    ensure_advisor_access(principal, advisor_id)
    repetitions = body.repetitions or settings.optimisation_default_repetitions
    if repetitions > settings.optimisation_max_repetitions:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_repetitions",
                "message": (
                    f"repetitions cannot exceed "
                    f"{settings.optimisation_max_repetitions}."
                ),
            },
        )
    resolved_request = body.model_copy(
        update={"advisor_id": advisor_id, "repetitions": repetitions}
    )
    try:
        job = manager.submit(
            owner_id=principal.principal_id,
            agent_type=agent_type,
            request=resolved_request,
        )
    except OptimisationJobConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "optimisation_conflict", "message": str(exc)},
        ) from exc

    audit.log(
        principal_id=principal.principal_id,
        action="queue",
        resource_type="optimisation_job",
        resource_id=job.job_id,
        request_id=getattr(request.state, "request_id", None),
        metadata={"agent_type": agent_type.value, "advisor_id": advisor_id},
    )
    return job


@router.get("/optimisations", response_model=OptimisationJobPage)
def list_optimisations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    job_status: OptimisationJobStatus | None = Query(default=None, alias="status"),
    owner_id: str | None = None,
    principal: Principal = Security(get_current_principal),
    store: OptimisationJobStore = Depends(optimisation_job_store),
) -> OptimisationJobPage:
    if not principal.has_role("admin"):
        owner_id = principal.principal_id
    items, total = store.list_jobs(
        page=page,
        page_size=page_size,
        owner_id=owner_id,
        status=job_status,
    )
    return OptimisationJobPage(
        items=items,
        page=page_metadata(page=page, page_size=page_size, total_items=total),
    )


@router.get(
    "/optimisations/{job_id}",
    response_model=OptimisationJobResponse,
)
def get_optimisation(
    job_id: str,
    principal: Principal = Security(get_current_principal),
    store: OptimisationJobStore = Depends(optimisation_job_store),
) -> OptimisationJobResponse:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Optimisation job not found."},
        )
    ensure_owner_access(principal, job.owner_id)
    return job


@router.get(
    "/optimisation-results",
    response_model=OptimisationResultPage,
)
def list_optimisation_results(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    owner_id: str | None = None,
    agent_type: AgentType | None = None,
    principal: Principal = Security(get_current_principal),
    store: PromptStore = Depends(prompt_store),
) -> OptimisationResultPage:
    if not principal.has_role("admin"):
        owner_id = principal.principal_id
    items, total = store.list_optimisation_results(
        page=page,
        page_size=page_size,
        owner_id=owner_id,
        agent_type=agent_type,
    )
    return OptimisationResultPage(
        items=items,
        page=page_metadata(page=page, page_size=page_size, total_items=total),
    )


@router.get(
    "/optimisation-results/{optimisation_id}",
    response_model=OptimisationResultResponse,
)
def get_optimisation_result(
    optimisation_id: int,
    principal: Principal = Security(get_current_principal),
    store: PromptStore = Depends(prompt_store),
) -> OptimisationResultResponse:
    result = store.get_optimisation_result(optimisation_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Optimisation result not found."},
        )
    ensure_owner_access(principal, result.owner_id)
    return result
