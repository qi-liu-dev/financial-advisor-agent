from __future__ import annotations

from backend.models.db_models import AgentRunRecord
from backend.models.schemas import (
    AgentRunDetail,
    AgentRunSummary,
    AgentType,
    AdvisorPreferences,
    ClientSummaryOutput,
    EvaluationResult,
    InvestmentReviewOutput,
    MeetingNotesOutput,
    RunInputSnapshot,
    TokenUsage,
)


_OUTPUT_MODELS = {
    AgentType.CLIENT_SUMMARY: ClientSummaryOutput,
    AgentType.MEETING_NOTES: MeetingNotesOutput,
    AgentType.INVESTMENT_REVIEW: InvestmentReviewOutput,
}


def run_summary(record: AgentRunRecord) -> AgentRunSummary:
    return AgentRunSummary(
        run_id=record.run_id,
        owner_id=record.owner_id,
        advisor_id=record.advisor_id,
        agent_type=AgentType(record.task_type),
        prompt_version=record.prompt_version,
        model_name=record.model_name,
        input_hash=record.input_hash,
        latency_ms=record.latency_ms,
        has_evaluation=record.evaluation_scores is not None,
        provider_request_id=record.provider_request_id,
        client_request_id=record.client_request_id,
        created_at=record.timestamp,
    )


def run_detail(record: AgentRunRecord) -> AgentRunDetail:
    agent_type = AgentType(record.task_type)
    summary = run_summary(record)
    return AgentRunDetail(
        **summary.model_dump(),
        full_input=RunInputSnapshot.model_validate(record.full_input),
        output=_OUTPUT_MODELS[agent_type].model_validate(record.output),
        token_usage=(
            TokenUsage.model_validate(record.token_usage)
            if record.token_usage is not None
            else None
        ),
        evaluation=(
            EvaluationResult.model_validate(record.evaluation_scores)
            if record.evaluation_scores is not None
            else None
        ),
        advisor_preferences=(
            AdvisorPreferences.model_validate(record.advisor_preferences)
            if record.advisor_preferences is not None
            else None
        ),
    )
