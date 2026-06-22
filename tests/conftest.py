from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_application_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("AUTH_MODE", "disabled")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("DATA_RETENTION_DAYS", "0")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DATA_ENCRYPTION_KEY", raising=False)

    from backend.config import get_settings
    from backend.llm import close_llm_client

    close_llm_client()
    get_settings.cache_clear()
    yield
    close_llm_client()
    get_settings.cache_clear()
