from __future__ import annotations

from typing import Any

from backend.agents.base import AgentRunResult
from backend.database import init_db
from backend.models.schemas import AgentType, ClientSummaryOutput, PromptStatus
from backend.optimisation.gepa_loop import GEPAInspiredOptimiser
from backend.traces.trace_logger import TraceLogger


class _DeterministicAgent:
    def run(self, *, prompt_version: str, **_: Any) -> AgentRunResult:
        return AgentRunResult(
            output=ClientSummaryOutput(
                summary="Synthetic summary covering retirement, liquidity, and single-stock concentration.",
                key_points=["Retirement planning and liquidity both matter."],
                risks=["Single-stock concentration requires human review."],
                next_actions=["Confirm liquidity timing."],
                confidence=0.8,
                citations_to_input=[
                    "client_profile.constraints",
                    "portfolio_summary.risk_notes",
                ],
                suitability_context=["Moderate risk tolerance."],
                missing_information=["Renovation date."],
            ),
            latency_ms=100.0,
            token_usage={"prompt_tokens": 10, "completion_tokens": 10},
            model_name="fake-model",
            prompt_version=prompt_version,
            provider_request_id=None,
            client_request_id="fake-request",
        )


def test_repeated_optimisation_records_variance_and_keeps_rejected_prompt_inactive(
    monkeypatch,
) -> None:
    init_db()
    monkeypatch.setattr(
        "backend.optimisation.gepa_loop.get_agent",
        lambda _: _DeterministicAgent(),
    )

    optimiser = GEPAInspiredOptimiser()
    result = optimiser.optimise(
        agent_type=AgentType.CLIENT_SUMMARY,
        advisor_id="demo-advisor",
        owner_id="demo-advisor",
        max_variants=1,
        benchmark_limit=1,
        repetitions=2,
    )

    assert result.baseline.metrics.sample_count == 2
    assert len(result.candidates) == 1
    assert result.candidates[0].metrics.sample_count == 2
    assert result.candidates[0].status == PromptStatus.REJECTED
    assert result.selected_versions == []
    assert optimiser.prompt_store.get_prompt(AgentType.CLIENT_SUMMARY)[1] == "baseline"

    runs, total = TraceLogger().list_runs_page(page=1, page_size=10)
    assert total == 4
    assert {run.full_input["repetition_index"] for run in runs} == {1, 2}
