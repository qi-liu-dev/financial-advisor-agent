from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from backend.database import database_health
from backend.llm import is_llm_configured
from backend.models.schemas import HealthComponent, HealthResponse
from backend.security.crypto import encryption_enabled


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request, response: Response) -> HealthResponse:
    settings = request.app.state.settings
    try:
        db = database_health()
        database_component = HealthComponent(status="ok")
    except Exception:
        db = {"migration_version": 0, "active_prompt_count": 0}
        database_component = HealthComponent(
            status="error",
            detail="Database readiness check failed.",
        )

    llm_ready = is_llm_configured(settings)
    if llm_ready:
        llm_component = HealthComponent(
            status="ok",
            detail="Static provider configuration is present; live provider access is checked on calls.",
        )
    else:
        llm_component = HealthComponent(
            status=("error" if settings.require_llm_for_readiness else "degraded"),
            detail="No complete LLM provider configuration is present.",
        )

    overall = "ok"
    if database_component.status == "error" or (
        settings.require_llm_for_readiness and not llm_ready
    ):
        overall = "error"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif llm_component.status == "degraded":
        # The API remains ready for offline rule-based evaluation and synthetic
        # data browsing when an LLM is optional. The component still exposes
        # the degraded provider state.
        overall = "ok"

    return HealthResponse(
        status=overall,
        service="financial-advisor-agent-optimizer",
        version="0.3.0",
        database=database_component,
        llm=llm_component,
        migration_version=int(db["migration_version"]),
        active_prompt_count=int(db["active_prompt_count"]),
        encryption_enabled=encryption_enabled(),
    )


@router.get("/health/live", response_model=HealthResponse, include_in_schema=False)
def liveness(request: Request, response: Response) -> HealthResponse:
    return health(request, response)


@router.get("/health/ready", response_model=HealthResponse, include_in_schema=False)
def readiness(request: Request, response: Response) -> HealthResponse:
    return health(request, response)
