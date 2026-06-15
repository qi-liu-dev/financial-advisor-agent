from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from backend.agents import BASELINE_PROMPTS
from backend.database import get_connection
from backend.models.schemas import AgentType


class PromptStore:
    def seed_baselines(self) -> None:
        for agent_type, prompt in BASELINE_PROMPTS.items():
            self.save_prompt_version(
                agent_type=agent_type,
                version="baseline",
                prompt=prompt,
                parent_version=None,
                reflection="Initial hand-written prompt.",
                average_scores=None,
                overwrite=False,
            )

    def save_prompt_version(
        self,
        *,
        agent_type: AgentType,
        version: str,
        prompt: str,
        parent_version: str | None,
        reflection: str | None,
        average_scores: dict[str, Any] | None,
        overwrite: bool = True,
    ) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        sql = (
            """
            INSERT INTO prompt_versions (
                agent_type, version, prompt, parent_version, reflection, average_scores, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_type, version) DO UPDATE SET
                prompt = excluded.prompt,
                parent_version = excluded.parent_version,
                reflection = excluded.reflection,
                average_scores = excluded.average_scores
            """
            if overwrite
            else """
            INSERT OR IGNORE INTO prompt_versions (
                agent_type, version, prompt, parent_version, reflection, average_scores, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
        )
        with get_connection() as conn:
            conn.execute(
                sql,
                (
                    agent_type.value,
                    version,
                    prompt,
                    parent_version,
                    reflection,
                    json.dumps(average_scores, sort_keys=True) if average_scores else None,
                    timestamp,
                ),
            )

    def get_prompt(self, agent_type: AgentType, version: str | None = None) -> tuple[str, str]:
        with get_connection() as conn:
            if version:
                row = conn.execute(
                    "SELECT prompt, version FROM prompt_versions WHERE agent_type = ? AND version = ?",
                    (agent_type.value, version),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT prompt, version FROM prompt_versions
                    WHERE agent_type = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (agent_type.value,),
                ).fetchone()
        if row is None:
            raise KeyError(f"No prompt version found for {agent_type.value}: {version or 'latest'}")
        return row["prompt"], row["version"]

    def list_prompt_versions(self, agent_type: AgentType) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT agent_type, version, prompt, parent_version, reflection, average_scores, created_at
                FROM prompt_versions
                WHERE agent_type = ?
                ORDER BY id DESC
                """,
                (agent_type.value,),
            ).fetchall()
        return [
            {
                "agent_type": row["agent_type"],
                "version": row["version"],
                "prompt": row["prompt"],
                "parent_version": row["parent_version"],
                "reflection": row["reflection"],
                "average_scores": json.loads(row["average_scores"]) if row["average_scores"] else None,
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def save_optimisation_result(
        self,
        *,
        agent_type: AgentType,
        baseline_version: str,
        selected_versions: list[str],
        comparison_results: dict[str, Any],
    ) -> int:
        timestamp = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO optimisation_results (
                    agent_type, baseline_version, selected_versions, comparison_results, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    agent_type.value,
                    baseline_version,
                    json.dumps(selected_versions, sort_keys=True),
                    json.dumps(comparison_results, sort_keys=True),
                    timestamp,
                ),
            )
            return int(cursor.lastrowid)
