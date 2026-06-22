from __future__ import annotations

from datetime import date as Date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def __contains__(self, item: object) -> bool:
        return isinstance(item, str) and item in type(self).model_fields

    def __getitem__(self, item: str):
        return getattr(self, item)


class AgentType(str, Enum):
    CLIENT_SUMMARY = "client_summary"
    MEETING_NOTES = "meeting_notes"
    INVESTMENT_REVIEW = "investment_review"


class PromptStatus(str, Enum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"
    SELECTED = "selected"
    REJECTED = "rejected"


class OptimisationJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BenchmarkDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class MockDatasetName(str, Enum):
    CLIENTS = "clients"
    PORTFOLIOS = "portfolios"
    MEETINGS = "meetings"
    INVESTMENT_PROPOSALS = "investment_proposals"


class AdvisorPreferences(StrictModel):
    summary_style: Literal["brief", "balanced", "narrative"] = "balanced"
    detail_level: Literal["low", "medium", "high"] = "medium"
    risk_focus: Literal["low", "balanced", "high"] = "balanced"
    preferred_language: str = "en"

    @field_validator("preferred_language")
    @classmethod
    def normalise_language(cls, value: str) -> str:
        value = value.strip().lower()
        return value or "en"


class ClientProfileData(StrictModel):
    client_id: str
    name: str | None = None
    age: int | None = Field(default=None, ge=0, le=130)
    household: str | None = None
    risk_tolerance: str
    investment_horizon_years: int | None = Field(default=None, ge=0)
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    notes: str | None = None


class PortfolioSummaryData(StrictModel):
    portfolio_id: str
    client_id: str | None = None
    currency: str | None = None
    total_value: float | None = Field(default=None, ge=0)
    asset_allocation: dict[str, float] = Field(default_factory=dict)
    risk_notes: list[str] = Field(default_factory=list)


class TranscriptTurn(StrictModel):
    turn_id: str
    speaker: str
    text: str


class MeetingData(StrictModel):
    meeting_id: str
    client_id: str
    date: Date | None = None
    transcript: list[TranscriptTurn] = Field(min_length=1)


class InvestmentProposalData(StrictModel):
    proposal_id: str
    client_id: str | None = None
    title: str
    proposal_summary: str
    intended_outcome: str | None = None
    known_open_questions: list[str] = Field(default_factory=list)


class ClientSummaryPayload(StrictModel):
    client_profile: ClientProfileData
    portfolio_summary: PortfolioSummaryData


class MeetingNotesPayload(StrictModel):
    meeting_id: str
    client_id: str
    transcript: list[TranscriptTurn] = Field(min_length=1)


class InvestmentReviewPayload(StrictModel):
    client_profile: ClientProfileData
    portfolio_summary: PortfolioSummaryData
    investment_proposal: InvestmentProposalData


TaskPayload = ClientSummaryPayload | MeetingNotesPayload | InvestmentReviewPayload
MockDataItem = ClientProfileData | PortfolioSummaryData | MeetingData | InvestmentProposalData


class BenchmarkExpectation(StrictModel):
    must_mention: list[str] = Field(default_factory=list)
    must_not_mention: list[str] = Field(default_factory=list)
    required_citations: list[str] = Field(default_factory=list)


class BenchmarkTaskResponse(StrictModel):
    task_id: str
    agent_type: AgentType
    difficulty: BenchmarkDifficulty
    tags: list[str]
    payload: TaskPayload
    expected: BenchmarkExpectation


class MockDataResponse(StrictModel):
    dataset: MockDatasetName
    synthetic_only: Literal[True] = True
    items: list[MockDataItem]


class ClientWorkspaceResponse(StrictModel):
    synthetic_only: Literal[True] = True
    client: ClientProfileData
    portfolios: list[PortfolioSummaryData]
    meetings: list[MeetingData]
    investment_proposals: list[InvestmentProposalData]


class BaseAgentOutput(StrictModel):
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


AgentOutput = ClientSummaryOutput | MeetingNotesOutput | InvestmentReviewOutput


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class MetricScore(StrictModel):
    score: int = Field(..., ge=1, le=5)
    feedback: str = Field(..., min_length=1)


class EvaluationProvenance(StrictModel):
    rule_based_enabled: bool = True
    benchmark_checks_enabled: bool
    llm_judge_enabled: bool
    llm_provider: str | None = None
    agent_model: str | None = None
    judge_model: str | None = None
    judge_is_distinct: bool | None = None
    caveat: str | None = None


class EvaluationResult(StrictModel):
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
    provenance: EvaluationProvenance | None = None


class RunAgentRequest(StrictModel):
    agent_type: AgentType
    advisor_id: str | None = None
    task_id: str | None = None
    payload: TaskPayload | None = None
    prompt_version: str | None = None
    preferences: AdvisorPreferences | None = None

    @model_validator(mode="after")
    def require_payload_or_task(self) -> RunAgentRequest:
        if self.payload is None and not self.task_id:
            raise ValueError("Either payload or task_id is required.")
        return self


class RunAgentResponse(StrictModel):
    run_id: str
    agent_type: AgentType
    advisor_id: str
    prompt_version: str
    output: AgentOutput
    latency_ms: float = Field(ge=0)
    token_usage: TokenUsage | None = None
    provider_request_id: str | None = None
    client_request_id: str | None = None
    created_at: datetime


class MemoryUpdateRequest(StrictModel):
    preferences: AdvisorPreferences


class AdvisorMemoryResponse(StrictModel):
    advisor_id: str
    preferences: AdvisorPreferences
    created_at: datetime
    updated_at: datetime


class OptimisationRequest(StrictModel):
    advisor_id: str | None = None
    max_variants: int = Field(default=3, ge=1, le=5)
    benchmark_limit: int | None = Field(default=None, ge=1)
    repetitions: int | None = Field(default=None, ge=1, le=10)


class OptimisationMetrics(StrictModel):
    quality: float = Field(ge=0)
    quality_stddev: float = Field(ge=0)
    safety: float = Field(ge=0)
    safety_stddev: float = Field(ge=0)
    latency_ms: float = Field(ge=0)
    latency_ms_stddev: float = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    estimated_cost_stddev: float = Field(ge=0)
    sample_count: int = Field(ge=0)


class PromptVersionResponse(StrictModel):
    agent_type: AgentType
    version: str
    prompt: str
    parent_version: str | None = None
    reflection: str | None = None
    average_scores: OptimisationMetrics | None = None
    status: PromptStatus
    is_active: bool
    selected_at: datetime | None = None
    activated_at: datetime | None = None
    created_at: datetime


# Backwards-compatible import name used by earlier code/tests.
PromptVersionRecord = PromptVersionResponse


class PromptActivationResponse(StrictModel):
    message: str
    prompt: PromptVersionResponse


class OptimisationSelectionPolicy(StrictModel):
    minimum_quality_delta: float = Field(ge=0)
    safety_tolerance: float = Field(ge=0)
    latency_tolerance_ratio: float = Field(ge=1)
    cost_tolerance_ratio: float = Field(ge=1)


class OptimisationBaselineResponse(StrictModel):
    version: str
    metrics: OptimisationMetrics
    run_ids: list[str]


class OptimisationCandidateResponse(StrictModel):
    version: str
    rationale: str
    metrics: OptimisationMetrics
    run_ids: list[str]
    status: PromptStatus
    qualifies: bool
    selected: bool
    reasons: list[str]


class OptimisationResultResponse(StrictModel):
    optimisation_id: int
    job_id: str | None = None
    owner_id: str
    agent_type: AgentType
    baseline: OptimisationBaselineResponse
    reflection: str
    candidates: list[OptimisationCandidateResponse]
    selected_versions: list[str]
    selection_policy: OptimisationSelectionPolicy
    selection_note: str
    created_at: datetime


class OptimisationJobResponse(StrictModel):
    job_id: str
    owner_id: str
    agent_type: AgentType
    status: OptimisationJobStatus
    progress: float = Field(ge=0, le=1)
    request: OptimisationRequest
    result_id: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RunInputSnapshot(StrictModel):
    task_id: str | None = None
    difficulty: BenchmarkDifficulty | None = None
    tags: list[str] = Field(default_factory=list)
    expected: BenchmarkExpectation | None = None
    payload: TaskPayload
    advisor_id: str
    advisor_preferences: AdvisorPreferences
    repetition_index: int | None = Field(default=None, ge=1)


class AgentRunSummary(StrictModel):
    run_id: str
    owner_id: str
    advisor_id: str
    agent_type: AgentType
    prompt_version: str
    model_name: str
    input_hash: str
    latency_ms: float
    has_evaluation: bool
    provider_request_id: str | None = None
    client_request_id: str | None = None
    created_at: datetime


class AgentRunDetail(AgentRunSummary):
    full_input: RunInputSnapshot
    output: AgentOutput
    token_usage: TokenUsage | None = None
    evaluation: EvaluationResult | None = None
    advisor_preferences: AdvisorPreferences | None = None


class PageMetadata(StrictModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class AgentRunPage(StrictModel):
    items: list[AgentRunSummary]
    page: PageMetadata


class PromptVersionPage(StrictModel):
    items: list[PromptVersionResponse]
    page: PageMetadata


class OptimisationJobPage(StrictModel):
    items: list[OptimisationJobResponse]
    page: PageMetadata


class OptimisationResultPage(StrictModel):
    items: list[OptimisationResultResponse]
    page: PageMetadata


class AuditEventResponse(StrictModel):
    id: int
    principal_id: str
    action: str
    resource_type: str
    resource_id: str | None = None
    request_id: str | None = None
    metadata: dict[str, str | int | float | bool | None] | None = None
    created_at: datetime


class AuditEventPage(StrictModel):
    items: list[AuditEventResponse]
    page: PageMetadata


class DeleteResponse(StrictModel):
    deleted: bool
    resource_id: str


class PurgeRunsResponse(StrictModel):
    deleted_count: int = Field(ge=0)
    older_than_days: int = Field(ge=0)


class HealthComponent(StrictModel):
    status: Literal["ok", "degraded", "error"]
    detail: str | None = None


class HealthResponse(StrictModel):
    status: Literal["ok", "degraded", "error"]
    service: str
    version: str
    database: HealthComponent
    llm: HealthComponent
    migration_version: int = Field(ge=0)
    active_prompt_count: int = Field(ge=0)
    encryption_enabled: bool


class ErrorDetail(StrictModel):
    code: str
    message: str
    client_request_id: str | None = None
    provider_request_id: str | None = None
    upstream_status_code: int | None = None


class ErrorResponse(StrictModel):
    detail: ErrorDetail


def page_metadata(*, page: int, page_size: int, total_items: int) -> PageMetadata:
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    return PageMetadata(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
