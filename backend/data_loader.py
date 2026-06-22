from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.config import DATA_DIR
from backend.models.schemas import (
    AgentType,
    BenchmarkTaskResponse,
    ClientProfileData,
    ClientWorkspaceResponse,
    InvestmentProposalData,
    MeetingData,
    MockDataItem,
    MockDatasetName,
    PortfolioSummaryData,
)


_DATASET_FILES: dict[MockDatasetName, str] = {
    MockDatasetName.CLIENTS: "mock_clients.json",
    MockDatasetName.PORTFOLIOS: "mock_portfolios.json",
    MockDatasetName.MEETINGS: "mock_meetings.json",
    MockDatasetName.INVESTMENT_PROPOSALS: "mock_investment_proposals.json",
}

_DATASET_MODELS = {
    MockDatasetName.CLIENTS: ClientProfileData,
    MockDatasetName.PORTFOLIOS: PortfolioSummaryData,
    MockDatasetName.MEETINGS: MeetingData,
    MockDatasetName.INVESTMENT_PROPOSALS: InvestmentProposalData,
}


def load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_benchmark_tasks() -> tuple[BenchmarkTaskResponse, ...]:
    raw = load_json_file(DATA_DIR / "benchmark_tasks.json")
    return tuple(BenchmarkTaskResponse.model_validate(item) for item in raw)


def list_tasks(agent_type: AgentType | None = None) -> list[BenchmarkTaskResponse]:
    tasks = list(load_benchmark_tasks())
    if agent_type is None:
        return tasks
    return [task for task in tasks if task.agent_type == agent_type]


def get_task(task_id: str) -> BenchmarkTaskResponse:
    for task in load_benchmark_tasks():
        if task.task_id == task_id:
            return task
    raise KeyError(f"Unknown task_id: {task_id}")


@lru_cache(maxsize=8)
def load_mock_dataset(dataset: MockDatasetName) -> tuple[MockDataItem, ...]:
    raw = load_json_file(DATA_DIR / _DATASET_FILES[dataset])
    model = _DATASET_MODELS[dataset]
    return tuple(model.model_validate(item) for item in raw)


def get_client_workspace(client_id: str) -> ClientWorkspaceResponse:
    clients = [
        item
        for item in load_mock_dataset(MockDatasetName.CLIENTS)
        if isinstance(item, ClientProfileData) and item.client_id == client_id
    ]
    if not clients:
        raise KeyError(f"Unknown synthetic client_id: {client_id}")

    portfolios = [
        item
        for item in load_mock_dataset(MockDatasetName.PORTFOLIOS)
        if isinstance(item, PortfolioSummaryData) and item.client_id == client_id
    ]
    meetings = [
        item
        for item in load_mock_dataset(MockDatasetName.MEETINGS)
        if isinstance(item, MeetingData) and item.client_id == client_id
    ]
    proposals = [
        item
        for item in load_mock_dataset(MockDatasetName.INVESTMENT_PROPOSALS)
        if isinstance(item, InvestmentProposalData) and item.client_id == client_id
    ]
    return ClientWorkspaceResponse(
        synthetic_only=True,
        client=clients[0],
        portfolios=portfolios,
        meetings=meetings,
        investment_proposals=proposals,
    )
