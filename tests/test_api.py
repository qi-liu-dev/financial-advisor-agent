from __future__ import annotations


def test_health_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.sqlite3"))

    from backend.config import get_settings

    get_settings.cache_clear()

    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
