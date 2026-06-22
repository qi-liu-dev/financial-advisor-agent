from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AgentRunRecord:
    run_id: str
    owner_id: str
    advisor_id: str
    task_type: str
    prompt_version: str
    model_name: str
    input_hash: str
    full_input: dict[str, Any]
    output: dict[str, Any]
    latency_ms: float
    token_usage: dict[str, Any] | None
    evaluation_scores: dict[str, Any] | None
    advisor_preferences: dict[str, Any] | None
    provider_request_id: str | None
    client_request_id: str | None
    timestamp: datetime


@dataclass(frozen=True)
class OptimisationJobRecord:
    job_id: str
    owner_id: str
    agent_type: str
    status: str
    progress: float
    request: dict[str, Any]
    result_id: int | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
