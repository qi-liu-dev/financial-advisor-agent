from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AgentType(str, Enum):
    CLIENT_SUMMARY = "client_summary"
    MEETING_NOTES = "meeting_notes"
    INVESTMENT_REVIEW = "investment_review"


class AdvisorPreferences(BaseModel):
    summary_style: Literal["brief", "balanced", "narrative"] = "balanced"
    detail_level: Literal["low", "medium", "high"] = "medium"
    risk_focus: Literal["low", "balanced", "high"] = "balanced"
    preferred_language: str = "en"

    @field_validator("preferred_language")
    @classmethod
    def normalise_language(cls, value: str) -> str:
        value = value.strip().lower()
        return value or "en"


class BaseAgentOutput(BaseModel):
    summary: str = Field(..., min_length=10)
    key_points: list[str] = Field(..., min_length=1)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    citations_to_input: list[str] = Field(default_factory=list)


class ClientSummaryOutput(BaseAgentOutput):
    suitability_context: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class MeetingNotesOutput(BaseAgentOutput):
    decisions: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class InvestmentReviewOutput(BaseAgentOutput):
    suitability_observations: list[str] = Field(default_factory=list)
    compliance_flags: list[str] = Field(default_factory=list)
    questions_for_advisor: list[str] = Field(default_factory=list)


class MetricScore(BaseModel):
    score: int = Field(..., ge=1, le=5)
    feedback: str = Field(..., min_length=1)


class EvaluationResult(BaseModel):
    faithfulness: MetricScore
    completeness: MetricScore
    risk_awareness: MetricScore
    clarity: MetricScore
    advisor_usefulness: MetricScore
    safety: MetricScore
    format_correctness: MetricScore
    benchmark_expectations: MetricScore | None = None
    latency_ms: float = Field(..., ge=0)
    estimated_cost: float = Field(..., ge=0)
    feedback: str


class RunAgentRequest(BaseModel):
    agent_type: AgentType
    advisor_id: str = "demo-advisor"
    task_id: str | None = None
    payload: dict[str, Any] | None = None
    prompt_version: str | None = None
    preferences: AdvisorPreferences | None = None


class RunAgentResponse(BaseModel):
    run_id: str
    agent_type: AgentType
    prompt_version: str
    output: dict[str, Any]
    latency_ms: float
    token_usage: dict[str, Any] | None = None
    provider_request_id: str | None = None
    client_request_id: str | None = None


class MemoryUpdateRequest(BaseModel):
    preferences: AdvisorPreferences


class OptimisationRequest(BaseModel):
    advisor_id: str = "demo-advisor"
    max_variants: int = Field(default=3, ge=1, le=5)
    benchmark_limit: int | None = Field(default=None, ge=1)


class PromptVersionRecord(BaseModel):
    agent_type: AgentType
    version: str
    prompt: str
    parent_version: str | None = None
    reflection: str | None = None
    average_scores: dict[str, Any] | None = None
    created_at: datetime
