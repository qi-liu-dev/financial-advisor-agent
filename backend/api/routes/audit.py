from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Security

from backend.api.dependencies import audit_repository
from backend.audit import AuditRepository
from backend.models.schemas import AuditEventPage, page_metadata
from backend.security.auth import Principal, require_admin


router = APIRouter(tags=["audit"])


@router.get("/audit-events", response_model=AuditEventPage)
def audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    principal_id: str | None = None,
    _: Principal = Security(require_admin),
    repository: AuditRepository = Depends(audit_repository),
) -> AuditEventPage:
    items, total = repository.list_events(
        page=page,
        page_size=page_size,
        principal_id=principal_id,
    )
    return AuditEventPage(
        items=items,
        page=page_metadata(page=page, page_size=page_size, total_items=total),
    )
