from __future__ import annotations

from fastapi import APIRouter

from backend.api.routes import audit, health, memory, optimisations, prompts, runs, tasks


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(tasks.router)
api_router.include_router(runs.router)
api_router.include_router(prompts.router)
api_router.include_router(optimisations.router)
api_router.include_router(memory.router)
api_router.include_router(audit.router)
