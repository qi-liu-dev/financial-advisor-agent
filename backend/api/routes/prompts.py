from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security

from backend.api.dependencies import audit_repository, prompt_store
from backend.audit import AuditRepository
from backend.models.schemas import (
    AgentType,
    PromptActivationResponse,
    PromptVersionPage,
    PromptVersionResponse,
    page_metadata,
)
from backend.optimisation.prompt_store import PromptStore
from backend.security.auth import (
    Principal,
    get_current_principal,
    require_admin,
)


router = APIRouter(tags=["prompts"])


@router.get(
    "/prompt-versions/{agent_type}",
    response_model=PromptVersionPage,
)
def prompt_versions(
    agent_type: AgentType,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _: Principal = Security(get_current_principal),
    store: PromptStore = Depends(prompt_store),
) -> PromptVersionPage:
    items, total = store.list_prompt_versions(
        agent_type,
        page=page,
        page_size=page_size,
    )
    return PromptVersionPage(
        items=items,
        page=page_metadata(page=page, page_size=page_size, total_items=total),
    )


@router.get(
    "/prompts/{agent_type}/active",
    response_model=PromptVersionResponse,
)
def active_prompt(
    agent_type: AgentType,
    _: Principal = Security(get_current_principal),
    store: PromptStore = Depends(prompt_store),
) -> PromptVersionResponse:
    _, version = store.get_prompt(agent_type)
    result = store.get_prompt_version(agent_type, version)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Active prompt not found."})
    return result


@router.post(
    "/prompts/{agent_type}/{version}/activate",
    response_model=PromptActivationResponse,
)
def activate_prompt(
    agent_type: AgentType,
    version: str,
    request: Request,
    principal: Principal = Security(require_admin),
    store: PromptStore = Depends(prompt_store),
    audit: AuditRepository = Depends(audit_repository),
) -> PromptActivationResponse:
    try:
        activated = store.activate_prompt(agent_type=agent_type, version=version)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "prompt_not_selectable", "message": str(exc)},
        ) from exc

    audit.log(
        principal_id=principal.principal_id,
        action="activate",
        resource_type="prompt_version",
        resource_id=f"{agent_type.value}:{version}",
        request_id=getattr(request.state, "request_id", None),
    )
    return PromptActivationResponse(
        message="Prompt activated explicitly.",
        prompt=activated,
    )
