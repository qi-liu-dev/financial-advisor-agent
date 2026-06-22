from __future__ import annotations

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.main import create_app


def test_in_process_rate_limit_returns_429(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        first = client.get("/api/v1/tasks")
        second = client.get("/api/v1/tasks")
        third = client.get("/api/v1/tasks")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.headers["retry-after"]
