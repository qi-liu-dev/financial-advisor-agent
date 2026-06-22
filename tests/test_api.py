from __future__ import annotations

import base64
import json
from typing import Any

from fastapi.testclient import TestClient

from backend.agents.base import AgentRunResult
from backend.config import get_settings
from backend.main import create_app
from backend.models.schemas import ClientSummaryOutput


def _client() -> TestClient:
    get_settings.cache_clear()
    return TestClient(create_app())


def _fake_agent_result() -> AgentRunResult:
    return AgentRunResult(
        output=ClientSummaryOutput(
            summary="Synthetic client summary with liquidity and retirement context.",
            key_points=["The portfolio has a concentrated single-stock position."],
            risks=["Concentration and liquidity timing require advisor review."],
            next_actions=["Confirm the renovation date with the client."],
            confidence=0.88,
            citations_to_input=[
                "client_profile.constraints",
                "portfolio_summary.risk_notes",
            ],
            suitability_context=["Moderate risk tolerance and ten-year horizon."],
            missing_information=["Exact renovation date."],
        ),
        latency_ms=125.0,
        token_usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
        model_name="fake-agent-model",
        prompt_version="baseline",
        provider_request_id="provider-1",
        client_request_id="client-1",
    )


class _FakeAgent:
    def run(self, **_: Any) -> AgentRunResult:
        return _fake_agent_result()


def test_health_endpoint_and_versioned_api() -> None:
    with _client() as client:
        root = client.get("/health")
        versioned = client.get("/api/v1/health")

    assert root.status_code == 200
    assert versioned.status_code == 200
    assert root.json()["status"] == "ok"
    assert root.json()["database"]["status"] == "ok"
    assert root.json()["migration_version"] >= 6


def test_cors_preflight_for_angular_origin(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:4200")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.options(
            "/api/v1/tasks",
            headers={
                "Origin": "http://localhost:4200",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:4200"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_api_key_authentication_and_advisor_isolation(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "api_key")
    monkeypatch.setenv(
        "API_KEYS_JSON",
        json.dumps(
            {
                "advisor-secret": {
                    "principal_id": "advisor-1",
                    "roles": ["advisor"],
                }
            }
        ),
    )
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        missing = client.get("/api/v1/tasks")
        allowed = client.get(
            "/api/v1/tasks",
            headers={"X-API-Key": "advisor-secret"},
        )
        own_memory = client.get(
            "/api/v1/memory/advisor-1",
            headers={"Authorization": "Bearer advisor-secret"},
        )
        other_memory = client.get(
            "/api/v1/memory/advisor-2",
            headers={"X-API-Key": "advisor-secret"},
        )

    assert missing.status_code == 401
    assert allowed.status_code == 200
    assert own_memory.status_code == 200
    assert other_memory.status_code == 403


def test_azure_easy_auth_principal_header(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "azure_easy_auth")
    get_settings.cache_clear()
    principal = base64.b64encode(
        json.dumps(
            {
                "userId": "entra-user-1",
                "userDetails": "advisor@example.com",
                "userRoles": ["advisor"],
            }
        ).encode("utf-8")
    ).decode("ascii")

    with TestClient(create_app()) as client:
        unauthenticated = client.get("/api/v1/tasks")
        authenticated = client.get(
            "/api/v1/tasks",
            headers={"X-MS-CLIENT-PRINCIPAL": principal},
        )

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200


def test_run_evaluate_list_and_detail_are_typed_and_private(monkeypatch) -> None:
    monkeypatch.setattr("backend.api.routes.runs.get_agent", lambda _: _FakeAgent())

    with _client() as client:
        run_response = client.post(
            "/api/v1/run-agent",
            json={
                "agent_type": "client_summary",
                "task_id": "client-summary-001",
            },
        )
        assert run_response.status_code == 200, run_response.text
        run_id = run_response.json()["run_id"]

        listed_before = client.get("/api/v1/runs")
        detail = client.get(f"/api/v1/runs/{run_id}")
        evaluated = client.post(f"/api/v1/evaluate-run/{run_id}")
        listed_after = client.get("/api/v1/runs")

    assert "full_input" not in listed_before.json()["items"][0]
    assert "output" not in listed_before.json()["items"][0]
    assert detail.json()["full_input"]["task_id"] == "client-summary-001"
    assert detail.json()["output"]["missing_information"] == ["Exact renovation date."]
    assert evaluated.status_code == 200
    assert evaluated.json()["benchmark_expectations"]["score"] == 5
    assert evaluated.json()["provenance"]["llm_judge_enabled"] is False
    assert listed_after.json()["items"][0]["has_evaluation"] is True


def test_mock_data_files_are_exposed_for_frontend_browser() -> None:
    with _client() as client:
        clients = client.get("/api/v1/mock-data/clients")
        workspace = client.get(
            "/api/v1/mock-data/workspaces/mock-client-001"
        )

    assert clients.status_code == 200
    assert clients.json()["synthetic_only"] is True
    assert workspace.status_code == 200
    assert workspace.json()["client"]["client_id"] == "mock-client-001"
    assert workspace.json()["portfolios"]


def test_openapi_uses_named_response_schemas() -> None:
    with _client() as client:
        schema = client.get("/openapi.json").json()

    expected_operations = [
        ("/api/v1/tasks", "get"),
        ("/api/v1/run-agent", "post"),
        ("/api/v1/runs", "get"),
        ("/api/v1/runs/{run_id}", "get"),
        ("/api/v1/prompt-versions/{agent_type}", "get"),
        ("/api/v1/optimisations/{agent_type}", "post"),
        ("/api/v1/optimisations/{job_id}", "get"),
        ("/api/v1/memory/{advisor_id}", "get"),
    ]
    for path, method in expected_operations:
        responses = schema["paths"][path][method]["responses"]
        success = responses.get("200") or responses.get("202")
        response_schema = success["content"]["application/json"]["schema"]
        assert response_schema
        assert response_schema != {}
