from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Security

from backend.api.dependencies import audit_repository, memory_repository
from backend.audit import AuditRepository
from backend.memory.advisor_memory import AdvisorMemoryRepository
from backend.models.schemas import (
    AdvisorMemoryResponse,
    DeleteResponse,
    MemoryUpdateRequest,
)
from backend.security.auth import (
    Principal,
    ensure_advisor_access,
    get_current_principal,
)


router = APIRouter(tags=["advisor memory"])


@router.get("/memory/{advisor_id}", response_model=AdvisorMemoryResponse)
def get_memory(
    advisor_id: str,
    request: Request,
    principal: Principal = Security(get_current_principal),
    repository: AdvisorMemoryRepository = Depends(memory_repository),
    audit: AuditRepository = Depends(audit_repository),
) -> AdvisorMemoryResponse:
    ensure_advisor_access(principal, advisor_id)
    result = repository.get_memory(advisor_id, create_if_missing=True)
    assert result is not None
    audit.log(
        principal_id=principal.principal_id,
        action="read",
        resource_type="advisor_memory",
        resource_id=advisor_id,
        request_id=getattr(request.state, "request_id", None),
    )
    return result


@router.post("/memory/{advisor_id}", response_model=AdvisorMemoryResponse)
def update_memory(
    advisor_id: str,
    body: MemoryUpdateRequest,
    request: Request,
    principal: Principal = Security(get_current_principal),
    repository: AdvisorMemoryRepository = Depends(memory_repository),
    audit: AuditRepository = Depends(audit_repository),
) -> AdvisorMemoryResponse:
    ensure_advisor_access(principal, advisor_id)
    result = repository.save_preferences(
        advisor_id,
        body.preferences,
        owner_id=principal.principal_id,
    )
    audit.log(
        principal_id=principal.principal_id,
        action="update",
        resource_type="advisor_memory",
        resource_id=advisor_id,
        request_id=getattr(request.state, "request_id", None),
    )
    return result


@router.delete("/memory/{advisor_id}", response_model=DeleteResponse)
def delete_memory(
    advisor_id: str,
    request: Request,
    principal: Principal = Security(get_current_principal),
    repository: AdvisorMemoryRepository = Depends(memory_repository),
    audit: AuditRepository = Depends(audit_repository),
) -> DeleteResponse:
    ensure_advisor_access(principal, advisor_id)
    deleted = repository.delete_memory(advisor_id)
    audit.log(
        principal_id=principal.principal_id,
        action="delete",
        resource_type="advisor_memory",
        resource_id=advisor_id,
        request_id=getattr(request.state, "request_id", None),
        metadata={"deleted": deleted},
    )
    return DeleteResponse(deleted=deleted, resource_id=advisor_id)
