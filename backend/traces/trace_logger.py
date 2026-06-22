from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.database import get_connection
from backend.models.db_models import AgentRunRecord
from backend.security.crypto import decode_json, encode_json


def stable_hash(payload: dict[str, Any]) -> str:
    serialised = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


class TraceLogger:
    def log_run(
        self,
        *,
        run_id: str,
        task_type: str,
        prompt_version: str,
        model_name: str,
        full_input: dict[str, Any],
        output: dict[str, Any],
        latency_ms: float,
        token_usage: dict[str, Any] | None,
        evaluation_scores: dict[str, Any] | None,
        advisor_preferences: dict[str, Any] | None,
        provider_request_id: str | None = None,
        client_request_id: str | None = None,
        owner_id: str = "demo-advisor",
        advisor_id: str = "demo-advisor",
    ) -> datetime:
        timestamp = datetime.now(timezone.utc)
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs (
                    run_id, owner_id, advisor_id, task_type, prompt_version,
                    model_name, input_hash, full_input, output, latency_ms,
                    token_usage, evaluation_scores, advisor_preferences,
                    provider_request_id, client_request_id, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    owner_id,
                    advisor_id,
                    task_type,
                    prompt_version,
                    model_name,
                    stable_hash(full_input),
                    encode_json(full_input),
                    encode_json(output),
                    latency_ms,
                    encode_json(token_usage) if token_usage else None,
                    encode_json(evaluation_scores) if evaluation_scores else None,
                    encode_json(advisor_preferences) if advisor_preferences else None,
                    provider_request_id,
                    client_request_id,
                    timestamp.isoformat(),
                ),
            )
        return timestamp

    def update_evaluation(self, run_id: str, evaluation_scores: dict[str, Any]) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                "UPDATE agent_runs SET evaluation_scores = ? WHERE run_id = ?",
                (encode_json(evaluation_scores), run_id),
            )
            return cursor.rowcount > 0

    def get_run(self, run_id: str) -> AgentRunRecord | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list_runs(self, limit: int = 50) -> list[AgentRunRecord]:
        items, _ = self.list_runs_page(page=1, page_size=limit)
        return items

    def list_runs_page(
        self,
        *,
        page: int,
        page_size: int,
        owner_id: str | None = None,
        advisor_id: str | None = None,
        task_type: str | None = None,
        evaluated: bool | None = None,
    ) -> tuple[list[AgentRunRecord], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if owner_id:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        if advisor_id:
            clauses.append("advisor_id = ?")
            params.append(advisor_id)
        if task_type:
            clauses.append("task_type = ?")
            params.append(task_type)
        if evaluated is True:
            clauses.append("evaluation_scores IS NOT NULL")
        elif evaluated is False:
            clauses.append("evaluation_scores IS NULL")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size

        with get_connection() as conn:
            total = int(
                conn.execute(
                    f"SELECT COUNT(*) AS count FROM agent_runs {where}",
                    tuple(params),
                ).fetchone()["count"]
            )
            rows = conn.execute(
                f"""
                SELECT * FROM agent_runs
                {where}
                ORDER BY timestamp DESC, run_id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, page_size, offset),
            ).fetchall()
        return [self._row_to_record(row) for row in rows], total

    def delete_run(self, run_id: str, *, owner_id: str | None = None) -> bool:
        with get_connection() as conn:
            if owner_id:
                cursor = conn.execute(
                    "DELETE FROM agent_runs WHERE run_id = ? AND owner_id = ?",
                    (run_id, owner_id),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM agent_runs WHERE run_id = ?",
                    (run_id,),
                )
            return cursor.rowcount > 0

    def purge_runs(self, *, older_than_days: int, owner_id: str | None = None) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        with get_connection() as conn:
            if owner_id:
                cursor = conn.execute(
                    "DELETE FROM agent_runs WHERE timestamp < ? AND owner_id = ?",
                    (cutoff, owner_id),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM agent_runs WHERE timestamp < ?",
                    (cutoff,),
                )
            return max(0, cursor.rowcount)

    def _row_to_record(self, row: Any) -> AgentRunRecord:
        keys = set(row.keys())
        return AgentRunRecord(
            run_id=row["run_id"],
            owner_id=row["owner_id"] if "owner_id" in keys else "demo-advisor",
            advisor_id=row["advisor_id"] if "advisor_id" in keys else "demo-advisor",
            task_type=row["task_type"],
            prompt_version=row["prompt_version"],
            model_name=row["model_name"],
            input_hash=row["input_hash"],
            full_input=decode_json(row["full_input"]),
            output=decode_json(row["output"]),
            latency_ms=float(row["latency_ms"]),
            token_usage=decode_json(row["token_usage"], default=None),
            evaluation_scores=decode_json(row["evaluation_scores"], default=None),
            advisor_preferences=decode_json(row["advisor_preferences"], default=None),
            provider_request_id=(
                row["provider_request_id"] if "provider_request_id" in keys else None
            ),
            client_request_id=(
                row["client_request_id"] if "client_request_id" in keys else None
            ),
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
