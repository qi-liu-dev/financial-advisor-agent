from __future__ import annotations

import sqlite3

from backend.config import get_settings
from backend.database import init_db
from backend.traces.trace_logger import TraceLogger


def test_existing_database_is_migrated_and_request_ids_are_persisted(
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "existing.sqlite3"
    with sqlite3.connect(database_path) as conn:
        conn.execute(
            """
            CREATE TABLE agent_runs (
                run_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                model_name TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                full_input TEXT NOT NULL,
                output TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                token_usage TEXT,
                evaluation_scores TEXT,
                advisor_preferences TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )

    monkeypatch.setenv("SQLITE_DB_PATH", str(database_path))
    get_settings.cache_clear()
    init_db()

    with sqlite3.connect(database_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(agent_runs)")
        }
    assert "provider_request_id" in columns
    assert "client_request_id" in columns

    TraceLogger().log_run(
        run_id="run-with-request-ids",
        task_type="client_summary",
        prompt_version="baseline",
        model_name="test-model",
        full_input={"payload": "synthetic"},
        output={"summary": "synthetic output"},
        latency_ms=12.3,
        token_usage={"prompt_tokens": 1, "completion_tokens": 2},
        evaluation_scores=None,
        advisor_preferences=None,
        provider_request_id="provider-id",
        client_request_id="client-id",
    )
    record = TraceLogger().get_run("run-with-request-ids")

    assert record is not None
    assert record.provider_request_id == "provider-id"
    assert record.client_request_id == "client-id"

    get_settings.cache_clear()
