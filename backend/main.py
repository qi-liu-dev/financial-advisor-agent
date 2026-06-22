from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.api.routes.health import health as versioned_health
from backend.config import Settings, get_settings
from backend.database import init_db
from backend.llm import close_llm_client
from backend.models.schemas import HealthResponse
from backend.optimisation.jobs import OptimisationJobManager, OptimisationJobStore
from backend.optimisation.prompt_store import PromptStore
from backend.security.middleware import InMemoryRateLimitMiddleware, RequestIdMiddleware
from backend.traces.trace_logger import TraceLogger


logger = logging.getLogger("financial_advisor.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        PromptStore().seed_baselines()
        orphaned = OptimisationJobStore().fail_orphaned_jobs()
        if orphaned:
            logger.warning("marked_orphaned_optimisation_jobs_failed count=%s", orphaned)
        if resolved_settings.data_retention_days > 0:
            deleted = TraceLogger().purge_runs(
                older_than_days=resolved_settings.data_retention_days
            )
            if deleted:
                logger.info("purged_expired_agent_runs count=%s", deleted)

        manager = OptimisationJobManager(
            max_workers=resolved_settings.optimisation_worker_count
        )
        app.state.optimisation_manager = manager
        try:
            yield
        finally:
            manager.shutdown(wait=True)
            close_llm_client()

    app = FastAPI(
        title="Financial Advisor Agent Optimizer",
        version="0.3.0",
        description=(
            "Typed, authenticated API for evaluating and GEPA-inspired prompt "
            "optimisation of synthetic financial-advisory LLM agents."
        ),
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_allowed_origins),
        allow_credentials=resolved_settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "X-Request-ID",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Window",
            "Retry-After",
        ],
    )
    app.add_middleware(
        InMemoryRateLimitMiddleware,
        enabled=resolved_settings.rate_limit_enabled,
        requests=resolved_settings.rate_limit_requests,
        window_seconds=resolved_settings.rate_limit_window_seconds,
        api_prefix=resolved_settings.api_prefix,
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(api_router, prefix=resolved_settings.api_prefix)

    # Stable root probe for Docker/Azure health checks. The application API
    # itself remains versioned under /api/v1.
    @app.get("/health", response_model=HealthResponse, include_in_schema=False)
    def root_health(request: Request, response: Response) -> HealthResponse:
        return versioned_health(request, response)

    return app


app = create_app()
