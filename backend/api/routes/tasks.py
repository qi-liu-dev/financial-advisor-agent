from __future__ import annotations

from fastapi import APIRouter, HTTPException, Security

from backend.data_loader import (
    get_client_workspace,
    list_tasks,
    load_mock_dataset,
)
from backend.models.schemas import (
    AgentType,
    BenchmarkTaskResponse,
    ClientWorkspaceResponse,
    MockDataResponse,
    MockDatasetName,
)
from backend.security.auth import Principal, get_current_principal


router = APIRouter(tags=["synthetic data"])


@router.get("/tasks", response_model=list[BenchmarkTaskResponse])
def tasks(
    agent_type: AgentType | None = None,
    _: Principal = Security(get_current_principal),
) -> list[BenchmarkTaskResponse]:
    return list_tasks(agent_type)


@router.get("/mock-data/{dataset}", response_model=MockDataResponse)
def mock_data(
    dataset: MockDatasetName,
    _: Principal = Security(get_current_principal),
) -> MockDataResponse:
    return MockDataResponse(
        dataset=dataset,
        synthetic_only=True,
        items=list(load_mock_dataset(dataset)),
    )


@router.get(
    "/mock-data/workspaces/{client_id}",
    response_model=ClientWorkspaceResponse,
)
def client_workspace(
    client_id: str,
    _: Principal = Security(get_current_principal),
) -> ClientWorkspaceResponse:
    try:
        return get_client_workspace(client_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": str(exc)},
        ) from exc
