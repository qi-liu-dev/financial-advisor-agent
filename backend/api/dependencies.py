from __future__ import annotations

from fastapi import Request

from backend.audit import AuditRepository
from backend.memory.advisor_memory import AdvisorMemoryRepository
from backend.optimisation.jobs import OptimisationJobManager, OptimisationJobStore
from backend.optimisation.prompt_store import PromptStore
from backend.traces.trace_logger import TraceLogger


def trace_logger() -> TraceLogger:
    return TraceLogger()


def prompt_store() -> PromptStore:
    return PromptStore()


def memory_repository() -> AdvisorMemoryRepository:
    return AdvisorMemoryRepository()


def audit_repository() -> AuditRepository:
    return AuditRepository()


def optimisation_job_store() -> OptimisationJobStore:
    return OptimisationJobStore()


def optimisation_job_manager(request: Request) -> OptimisationJobManager:
    return request.app.state.optimisation_manager
