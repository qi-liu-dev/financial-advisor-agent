from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from backend.config import get_settings


def _database_path() -> Path:
    path = get_settings().sqlite_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_database_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
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
                provider_request_id TEXT,
                client_request_id TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )
        # Lightweight, idempotent migration for repositories that already have
        # an optimizer.sqlite3 created by the pre-refactor schema.
        _ensure_column(conn, "agent_runs", "provider_request_id", "TEXT")
        _ensure_column(conn, "agent_runs", "client_request_id", "TEXT")

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


def _ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    existing_columns = {
        row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")
    }
    if column_name not in existing_columns:
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )
