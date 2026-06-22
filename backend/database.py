from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import get_settings
from backend.security.crypto import validate_encryption_configuration


Migration = tuple[int, str, Callable[[sqlite3.Connection], None]]


def _database_path() -> Path:
    path = get_settings().sqlite_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    conn = sqlite3.connect(
        _database_path(),
        timeout=settings.database_busy_timeout_ms / 1000,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {settings.database_busy_timeout_ms}")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    validate_encryption_configuration()
    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        applied = {
            int(row["version"])
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for version, name, migration in MIGRATIONS:
            if version in applied:
                continue
            migration(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, _utc_now()),
            )


def database_health() -> dict[str, Any]:
    with get_connection() as conn:
        conn.execute("SELECT 1").fetchone()
        migration = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
        ).fetchone()
        active_prompts = conn.execute(
            "SELECT COUNT(*) AS count FROM prompt_versions WHERE is_active = 1"
        ).fetchone()
    return {
        "status": "ok",
        "migration_version": int(migration["version"]),
        "active_prompt_count": int(active_prompts["count"]),
    }


def _migration_001_base(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_runs (
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prompt_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_type TEXT NOT NULL,
            version TEXT NOT NULL,
            prompt TEXT NOT NULL,
            parent_version TEXT,
            reflection TEXT,
            average_scores TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(agent_type, version)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS advisor_memory (
            advisor_id TEXT PRIMARY KEY,
            preferences TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS optimisation_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_type TEXT NOT NULL,
            baseline_version TEXT NOT NULL,
            selected_versions TEXT NOT NULL,
            comparison_results TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _migration_002_llm_request_ids(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "agent_runs", "provider_request_id", "TEXT")
    _ensure_column(conn, "agent_runs", "client_request_id", "TEXT")


def _migration_003_prompt_lifecycle(conn: sqlite3.Connection) -> None:
    _ensure_column(
        conn,
        "prompt_versions",
        "status",
        "TEXT NOT NULL DEFAULT 'candidate'",
    )
    _ensure_column(
        conn,
        "prompt_versions",
        "is_active",
        "INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(conn, "prompt_versions", "selected_at", "TEXT")
    _ensure_column(conn, "prompt_versions", "activated_at", "TEXT")

    conn.execute(
        "UPDATE prompt_versions SET status = 'baseline' WHERE version = 'baseline'"
    )
    _mark_historically_selected_prompts(conn)

    agent_types = [
        row["agent_type"]
        for row in conn.execute(
            "SELECT DISTINCT agent_type FROM prompt_versions"
        ).fetchall()
    ]
    for agent_type in agent_types:
        has_active = conn.execute(
            "SELECT 1 FROM prompt_versions WHERE agent_type = ? AND is_active = 1 LIMIT 1",
            (agent_type,),
        ).fetchone()
        if has_active:
            continue
        baseline = conn.execute(
            """
            SELECT id FROM prompt_versions
            WHERE agent_type = ? AND version = 'baseline'
            LIMIT 1
            """,
            (agent_type,),
        ).fetchone()
        if baseline:
            conn.execute(
                "UPDATE prompt_versions SET is_active = 1, activated_at = ? WHERE id = ?",
                (_utc_now(), baseline["id"]),
            )

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_one_active_per_agent
        ON prompt_versions(agent_type)
        WHERE is_active = 1
        """
    )


def _migration_004_security_jobs_and_audit(conn: sqlite3.Connection) -> None:
    _ensure_column(
        conn,
        "agent_runs",
        "owner_id",
        "TEXT NOT NULL DEFAULT 'demo-advisor'",
    )
    _ensure_column(
        conn,
        "agent_runs",
        "advisor_id",
        "TEXT NOT NULL DEFAULT 'demo-advisor'",
    )
    _ensure_column(
        conn,
        "advisor_memory",
        "owner_id",
        "TEXT NOT NULL DEFAULT 'demo-advisor'",
    )
    _ensure_column(conn, "advisor_memory", "created_at", "TEXT")
    conn.execute(
        "UPDATE advisor_memory SET owner_id = advisor_id WHERE owner_id = 'demo-advisor'"
    )
    conn.execute(
        "UPDATE advisor_memory SET created_at = updated_at WHERE created_at IS NULL"
    )

    _ensure_column(
        conn,
        "optimisation_results",
        "owner_id",
        "TEXT NOT NULL DEFAULT 'demo-advisor'",
    )
    _ensure_column(conn, "optimisation_results", "job_id", "TEXT")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS optimisation_jobs (
            job_id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            agent_type TEXT NOT NULL,
            status TEXT NOT NULL,
            progress REAL NOT NULL DEFAULT 0,
            request_json TEXT NOT NULL,
            result_id INTEGER,
            error_code TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            FOREIGN KEY(result_id) REFERENCES optimisation_results(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            principal_id TEXT NOT NULL,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT,
            request_id TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL
        )
        """
    )


def _migration_005_indexes(conn: sqlite3.Connection) -> None:
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_runs_owner_timestamp ON agent_runs(owner_id, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_runs_advisor_timestamp ON agent_runs(advisor_id, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_runs_task_type ON agent_runs(task_type)",
        "CREATE INDEX IF NOT EXISTS idx_runs_prompt_version ON agent_runs(prompt_version)",
        "CREATE INDEX IF NOT EXISTS idx_prompt_agent_status ON prompt_versions(agent_type, status)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_owner_created ON optimisation_jobs(owner_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_status ON optimisation_jobs(status)",
        "CREATE INDEX IF NOT EXISTS idx_results_owner_created ON optimisation_results(owner_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_audit_principal_created ON audit_events(principal_id, created_at DESC)",
    ]
    for statement in index_statements:
        conn.execute(statement)


def _migration_006_job_concurrency_guard(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_job_per_owner_agent
        ON optimisation_jobs(owner_id, agent_type)
        WHERE status IN ('queued', 'running')
        """
    )


def _mark_historically_selected_prompts(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "optimisation_results"):
        return
    rows = conn.execute(
        "SELECT agent_type, selected_versions FROM optimisation_results"
    ).fetchall()
    for row in rows:
        try:
            versions = json.loads(row["selected_versions"])
        except (TypeError, json.JSONDecodeError):
            continue
        for version in versions if isinstance(versions, list) else []:
            conn.execute(
                """
                UPDATE prompt_versions
                SET status = 'selected', selected_at = COALESCE(selected_at, ?)
                WHERE agent_type = ? AND version = ?
                """,
                (_utc_now(), row["agent_type"], str(version)),
            )


def _ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    if not _table_exists(conn, table_name):
        return
    existing_columns = {
        row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")
    }
    if column_name not in existing_columns:
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


MIGRATIONS: tuple[Migration, ...] = (
    (1, "base_schema", _migration_001_base),
    (2, "llm_request_ids", _migration_002_llm_request_ids),
    (3, "prompt_lifecycle", _migration_003_prompt_lifecycle),
    (4, "security_jobs_and_audit", _migration_004_security_jobs_and_audit),
    (5, "query_indexes", _migration_005_indexes),
    (6, "optimisation_job_concurrency_guard", _migration_006_job_concurrency_guard),
)
