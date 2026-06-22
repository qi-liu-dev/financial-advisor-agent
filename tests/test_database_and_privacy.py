from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from cryptography.fernet import Fernet

from backend.config import get_settings
from backend.database import get_connection, init_db
from backend.models.schemas import AgentType
from backend.optimisation.prompt_store import PromptStore
from backend.traces.trace_logger import TraceLogger


def _log_run(run_id: str, owner_id: str) -> None:
    TraceLogger().log_run(
        run_id=run_id,
        owner_id=owner_id,
        advisor_id=owner_id,
        task_type="client_summary",
        prompt_version="baseline",
        model_name="fake",
        full_input={
            "task_id": None,
            "difficulty": None,
            "tags": [],
            "expected": None,
            "payload": {
                "client_profile": {
                    "client_id": "synthetic",
                    "risk_tolerance": "moderate",
                    "goals": [],
                    "constraints": [],
                },
                "portfolio_summary": {
                    "portfolio_id": "synthetic",
                    "asset_allocation": {},
                    "risk_notes": [],
                },
            },
            "advisor_id": owner_id,
            "advisor_preferences": {
                "summary_style": "balanced",
                "detail_level": "medium",
                "risk_focus": "balanced",
                "preferred_language": "en",
            },
            "repetition_index": None,
        },
        output={"summary": "synthetic"},
        latency_ms=1,
        token_usage=None,
        evaluation_scores=None,
        advisor_preferences=None,
    )


def test_sensitive_json_can_be_encrypted_at_rest(monkeypatch) -> None:
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    get_settings.cache_clear()
    init_db()
    _log_run("encrypted-run", "advisor-1")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT full_input, output FROM agent_runs WHERE run_id = 'encrypted-run'"
        ).fetchone()

    assert row["full_input"].startswith("enc:v1:")
    assert row["output"].startswith("enc:v1:")
    decoded = TraceLogger().get_run("encrypted-run")
    assert decoded is not None
    assert decoded.full_input["advisor_id"] == "advisor-1"


def test_run_repository_paginates_and_filters_by_owner() -> None:
    init_db()
    _log_run("owner-1-a", "owner-1")
    _log_run("owner-1-b", "owner-1")
    _log_run("owner-2-a", "owner-2")

    first_page, total = TraceLogger().list_runs_page(
        page=1,
        page_size=1,
        owner_id="owner-1",
    )

    assert total == 2
    assert len(first_page) == 1
    assert first_page[0].owner_id == "owner-1"


def test_versioned_migrations_fix_existing_prompt_activation(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
    get_settings.cache_clear()

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE prompt_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_type TEXT NOT NULL,
            version TEXT NOT NULL,
            prompt TEXT NOT NULL,
            parent_version TEXT,
            reflection TEXT,
            average_scores TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(agent_type, version)
        );
        CREATE TABLE optimisation_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_type TEXT NOT NULL,
            baseline_version TEXT NOT NULL,
            selected_versions TEXT NOT NULL,
            comparison_results TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO prompt_versions (agent_type, version, prompt, created_at) VALUES (?, ?, ?, ?)",
        ("client_summary", "baseline", "baseline prompt", now),
    )
    conn.execute(
        "INSERT INTO prompt_versions (agent_type, version, prompt, created_at) VALUES (?, ?, ?, ?)",
        ("client_summary", "unselected-latest", "candidate prompt", now),
    )
    conn.commit()
    conn.close()

    init_db()
    store = PromptStore()
    active_prompt, active_version = store.get_prompt(AgentType.CLIENT_SUMMARY)

    assert active_prompt == "baseline prompt"
    assert active_version == "baseline"
    candidate = store.get_prompt_version(
        AgentType.CLIENT_SUMMARY,
        "unselected-latest",
    )
    assert candidate is not None
    assert not candidate.is_active

    with get_connection() as migrated:
        versions = migrated.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        indexes = {
            row["name"]
            for row in migrated.execute("PRAGMA index_list(agent_runs)").fetchall()
        }

    assert [row["version"] for row in versions] == [1, 2, 3, 4, 5, 6]
    assert "idx_runs_owner_timestamp" in indexes
