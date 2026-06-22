from __future__ import annotations

import time
from threading import Event
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.database import init_db
from backend.main import create_app
from backend.models.schemas import (
    AgentType,
    OptimisationJobStatus,
    OptimisationMetrics,
    OptimisationRequest,
)
from backend.optimisation.jobs import (
    OptimisationJobConflict,
    OptimisationJobManager,
    OptimisationJobStore,
)
from backend.optimisation.prompt_store import PromptStore


def _comparison() -> dict[str, Any]:
    metrics = OptimisationMetrics(
        quality=4.0,
        quality_stddev=0.1,
        safety=5.0,
        safety_stddev=0.0,
        latency_ms=1000,
        latency_ms_stddev=50,
        estimated_cost=0.001,
        estimated_cost_stddev=0.00001,
        sample_count=2,
    )
    return {
        "baseline": {
            "version": "baseline",
            "metrics": metrics.model_dump(mode="json"),
            "run_ids": [],
        },
        "reflection": "Synthetic reflection.",
        "candidates": [],
        "selected_versions": [],
        "selection_policy": {
            "minimum_quality_delta": 0.05,
            "safety_tolerance": 0.0,
            "latency_tolerance_ratio": 1.2,
            "cost_tolerance_ratio": 1.1,
        },
        "selection_note": "No candidate selected; active prompt remains unchanged.",
    }


class _FakeOptimiser:
    def __init__(self, gate: Event | None = None, started: Event | None = None) -> None:
        self.gate = gate
        self.started = started

    def optimise(self, **kwargs: Any):
        if self.started:
            self.started.set()
        if self.gate:
            self.gate.wait(timeout=3)
        store = PromptStore()
        store.seed_baselines()
        optimisation_id, _ = store.save_optimisation_result(
            owner_id=kwargs["owner_id"],
            job_id=kwargs["job_id"],
            agent_type=kwargs["agent_type"],
            baseline_version="baseline",
            selected_versions=[],
            comparison_results=_comparison(),
        )
        result = store.get_optimisation_result(optimisation_id)
        assert result is not None
        return result


def _wait_for_terminal(store: OptimisationJobStore, job_id: str):
    deadline = time.time() + 5
    while time.time() < deadline:
        job = store.get_job(job_id)
        if job and job.status in {
            OptimisationJobStatus.COMPLETED,
            OptimisationJobStatus.FAILED,
        }:
            return job
        time.sleep(0.02)
    raise AssertionError("Job did not finish")


def test_async_optimisation_endpoint_returns_persisted_job() -> None:
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        original_manager = app.state.optimisation_manager
        original_manager.shutdown(wait=True)
        fake_manager = OptimisationJobManager(
            max_workers=1,
            optimiser_factory=lambda: _FakeOptimiser(),
        )
        app.state.optimisation_manager = fake_manager
        try:
            response = client.post(
                "/api/v1/optimisations/client_summary",
                json={"max_variants": 1, "benchmark_limit": 1, "repetitions": 2},
            )
            assert response.status_code == 202, response.text
            job_id = response.json()["job_id"]
            final = _wait_for_terminal(fake_manager.store, job_id)
            status_response = client.get(f"/api/v1/optimisations/{job_id}")
            result_response = client.get(
                f"/api/v1/optimisation-results/{final.result_id}"
            )
        finally:
            fake_manager.shutdown(wait=True)

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"
    assert result_response.status_code == 200
    assert result_response.json()["baseline"]["metrics"]["sample_count"] == 2


def test_concurrent_duplicate_optimisation_is_rejected() -> None:
    init_db()
    gate = Event()
    started = Event()
    manager = OptimisationJobManager(
        max_workers=2,
        optimiser_factory=lambda: _FakeOptimiser(gate=gate, started=started),
    )
    request = OptimisationRequest(
        advisor_id="advisor-1",
        max_variants=1,
        benchmark_limit=1,
        repetitions=1,
    )
    try:
        first = manager.submit(
            owner_id="advisor-1",
            agent_type=AgentType.CLIENT_SUMMARY,
            request=request,
        )
        assert started.wait(timeout=2)
        with pytest.raises(OptimisationJobConflict):
            manager.submit(
                owner_id="advisor-1",
                agent_type=AgentType.CLIENT_SUMMARY,
                request=request,
            )

        second_agent = manager.submit(
            owner_id="advisor-1",
            agent_type=AgentType.MEETING_NOTES,
            request=request,
        )
        gate.set()
        assert _wait_for_terminal(manager.store, first.job_id).status == OptimisationJobStatus.COMPLETED
        assert _wait_for_terminal(manager.store, second_agent.job_id).status == OptimisationJobStatus.COMPLETED
    finally:
        gate.set()
        manager.shutdown(wait=True)
