from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.config import DATA_DIR
from backend.models.schemas import AgentType


def load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=8)
def load_benchmark_tasks() -> list[dict[str, Any]]:
    return load_json_file(DATA_DIR / "benchmark_tasks.json")


def list_tasks(agent_type: AgentType | None = None) -> list[dict[str, Any]]:
    tasks = load_benchmark_tasks()
    if agent_type is None:
        return tasks
    return [task for task in tasks if task["agent_type"] == agent_type.value]


def get_task(task_id: str) -> dict[str, Any]:
    for task in load_benchmark_tasks():
        if task["task_id"] == task_id:
            return task
    raise KeyError(f"Unknown task_id: {task_id}")
