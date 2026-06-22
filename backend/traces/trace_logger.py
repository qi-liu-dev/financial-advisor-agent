from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from backend.database import get_connection
from backend.models.db_models import AgentRunRecord


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
    ) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs (
                    run_id, task_type, prompt_version, model_name, input_hash,
                    full_input, output, latency_ms, token_usage,
                    evaluation_scores, advisor_preferences, provider_request_id,
                    client_request_id, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    task_type,
                    prompt_version,
                    model_name,
                    stable_hash(full_input),
                    json.dumps(full_input, sort_keys=True),
                    json.dumps(output, sort_keys=True),
                    latency_ms,
                    json.dumps(token_usage, sort_keys=True) if token_usage else None,
                    json.dumps(evaluation_scores, sort_keys=True)
                    if evaluation_scores
                    else None,
                    json.dumps(advisor_preferences, sort_keys=True)
                    if advisor_preferences
                    else None,
                    provider_request_id,
                    client_request_id,
                    timestamp,
                ),
            )

    def update_evaluation(self, run_id: str, evaluation_scores: dict[str, Any]) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE agent_runs SET evaluation_scores = ? WHERE run_id = ?",
                (json.dumps(evaluation_scores, sort_keys=True), run_id),
            )

    def get_run(self, run_id: str) -> AgentRunRecord | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM agent_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list_runs(self, limit: int = 50) -> list[AgentRunRecord]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_runs ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: Any) -> AgentRunRecord:
        return AgentRunRecord(
            run_id=row["run_id"],
            task_type=row["task_type"],
            prompt_version=row["prompt_version"],
            model_name=row["model_name"],
            input_hash=row["input_hash"],
            full_input=json.loads(row["full_input"]),
            output=json.loads(row["output"]),
            latency_ms=float(row["latency_ms"]),
            token_usage=json.loads(row["token_usage"]) if row["token_usage"] else None,
            evaluation_scores=(
                json.loads(row["evaluation_scores"])
                if row["evaluation_scores"]
                else None
            ),
            advisor_preferences=(
                json.loads(row["advisor_preferences"])
                if row["advisor_preferences"]
                else None
            ),
            provider_request_id=row["provider_request_id"],
            client_request_id=row["client_request_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
