from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.agents import BASELINE_PROMPTS
from backend.database import get_connection
from backend.models.schemas import (
    AgentType,
    OptimisationResultResponse,
    PromptStatus,
    PromptVersionResponse,
)
from backend.security.crypto import decode_json, encode_json


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
                status=PromptStatus.BASELINE,
                overwrite=False,
            )
            with get_connection() as conn:
                active = conn.execute(
                    "SELECT 1 FROM prompt_versions WHERE agent_type = ? AND is_active = 1",
                    (agent_type.value,),
                ).fetchone()
                if not active:
                    conn.execute(
                        """
                        UPDATE prompt_versions
                        SET is_active = 1, activated_at = ?
                        WHERE agent_type = ? AND version = 'baseline'
                        """,
                        (_utc_now(), agent_type.value),
                    )

    def save_prompt_version(
        self,
        *,
        agent_type: AgentType,
        version: str,
        prompt: str,
        parent_version: str | None,
        reflection: str | None,
        average_scores: dict[str, Any] | Any | None,
        status: PromptStatus = PromptStatus.CANDIDATE,
        overwrite: bool = True,
    ) -> PromptVersionResponse:
        timestamp = _utc_now()
        encoded_scores = None
        if average_scores is not None:
            payload = (
                average_scores.model_dump()
                if hasattr(average_scores, "model_dump")
                else average_scores
            )
            encoded_scores = encode_json(payload)

        with get_connection() as conn:
            if overwrite:
                conn.execute(
                    """
                    INSERT INTO prompt_versions (
                        agent_type, version, prompt, parent_version, reflection,
                        average_scores, status, is_active, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                    ON CONFLICT(agent_type, version) DO UPDATE SET
                        prompt = excluded.prompt,
                        parent_version = excluded.parent_version,
                        reflection = excluded.reflection,
                        average_scores = excluded.average_scores,
                        status = CASE
                            WHEN prompt_versions.status = 'baseline' THEN 'baseline'
                            ELSE excluded.status
                        END
                    """,
                    (
                        agent_type.value,
                        version,
                        prompt,
                        parent_version,
                        reflection,
                        encoded_scores,
                        status.value,
                        timestamp,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO prompt_versions (
                        agent_type, version, prompt, parent_version, reflection,
                        average_scores, status, is_active, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        agent_type.value,
                        version,
                        prompt,
                        parent_version,
                        reflection,
                        encoded_scores,
                        status.value,
                        timestamp,
                    ),
                )
        result = self.get_prompt_version(agent_type, version)
        if result is None:
            raise RuntimeError("Prompt version was not persisted.")
        return result

    def get_prompt(
        self,
        agent_type: AgentType,
        version: str | None = None,
    ) -> tuple[str, str]:
        with get_connection() as conn:
            if version:
                row = conn.execute(
                    """
                    SELECT prompt, version FROM prompt_versions
                    WHERE agent_type = ? AND version = ?
                    """,
                    (agent_type.value, version),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT prompt, version FROM prompt_versions
                    WHERE agent_type = ? AND is_active = 1
                    LIMIT 1
                    """,
                    (agent_type.value,),
                ).fetchone()
        if row is None:
            target = version or "active"
            raise KeyError(f"No {target} prompt found for {agent_type.value}.")
        return row["prompt"], row["version"]

    def get_prompt_version(
        self,
        agent_type: AgentType,
        version: str,
    ) -> PromptVersionResponse | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM prompt_versions WHERE agent_type = ? AND version = ?",
                (agent_type.value, version),
            ).fetchone()
        return self._row_to_prompt(row) if row else None

    def list_prompt_versions(
        self,
        agent_type: AgentType,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[PromptVersionResponse], int]:
        offset = (page - 1) * page_size
        with get_connection() as conn:
            total = int(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM prompt_versions WHERE agent_type = ?",
                    (agent_type.value,),
                ).fetchone()["count"]
            )
            rows = conn.execute(
                """
                SELECT * FROM prompt_versions
                WHERE agent_type = ?
                ORDER BY is_active DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (agent_type.value, page_size, offset),
            ).fetchall()
        return [self._row_to_prompt(row) for row in rows], total

    def mark_candidate_selection(
        self,
        *,
        agent_type: AgentType,
        candidate_versions: list[str],
        selected_versions: list[str],
    ) -> None:
        selected = set(selected_versions)
        timestamp = _utc_now()
        with get_connection() as conn:
            for version in candidate_versions:
                if version in selected:
                    conn.execute(
                        """
                        UPDATE prompt_versions
                        SET status = 'selected', selected_at = ?
                        WHERE agent_type = ? AND version = ? AND status != 'baseline'
                        """,
                        (timestamp, agent_type.value, version),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE prompt_versions
                        SET status = 'rejected', selected_at = NULL
                        WHERE agent_type = ? AND version = ? AND status != 'baseline'
                        """,
                        (agent_type.value, version),
                    )

    def activate_prompt(
        self,
        *,
        agent_type: AgentType,
        version: str,
    ) -> PromptVersionResponse:
        timestamp = _utc_now()
        with get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT status FROM prompt_versions
                WHERE agent_type = ? AND version = ?
                """,
                (agent_type.value, version),
            ).fetchone()
            if row is None:
                raise KeyError(
                    f"No prompt version found for {agent_type.value}: {version}"
                )
            if row["status"] not in {
                PromptStatus.BASELINE.value,
                PromptStatus.SELECTED.value,
            }:
                raise ValueError(
                    "Only baseline or selected prompt versions can be activated."
                )
            conn.execute(
                "UPDATE prompt_versions SET is_active = 0 WHERE agent_type = ?",
                (agent_type.value,),
            )
            conn.execute(
                """
                UPDATE prompt_versions
                SET is_active = 1, activated_at = ?
                WHERE agent_type = ? AND version = ?
                """,
                (timestamp, agent_type.value, version),
            )
        result = self.get_prompt_version(agent_type, version)
        if result is None:
            raise RuntimeError("Activated prompt version disappeared.")
        return result

    def save_optimisation_result(
        self,
        *,
        owner_id: str,
        job_id: str | None,
        agent_type: AgentType,
        baseline_version: str,
        selected_versions: list[str],
        comparison_results: dict[str, Any],
    ) -> tuple[int, datetime]:
        created_at = datetime.now(timezone.utc)
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO optimisation_results (
                    job_id, owner_id, agent_type, baseline_version,
                    selected_versions, comparison_results, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    owner_id,
                    agent_type.value,
                    baseline_version,
                    encode_json(selected_versions),
                    encode_json(comparison_results),
                    created_at.isoformat(),
                ),
            )
            return int(cursor.lastrowid), created_at

    def get_optimisation_result(
        self,
        optimisation_id: int,
    ) -> OptimisationResultResponse | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM optimisation_results WHERE id = ?",
                (optimisation_id,),
            ).fetchone()
        return self._row_to_result(row) if row else None

    def list_optimisation_results(
        self,
        *,
        page: int,
        page_size: int,
        owner_id: str | None = None,
        agent_type: AgentType | None = None,
    ) -> tuple[list[OptimisationResultResponse], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if owner_id:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        if agent_type:
            clauses.append("agent_type = ?")
            params.append(agent_type.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size
        with get_connection() as conn:
            total = int(
                conn.execute(
                    f"SELECT COUNT(*) AS count FROM optimisation_results {where}",
                    tuple(params),
                ).fetchone()["count"]
            )
            rows = conn.execute(
                f"""
                SELECT * FROM optimisation_results
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, page_size, offset),
            ).fetchall()
        return [self._row_to_result(row) for row in rows], total

    def _row_to_prompt(self, row: Any) -> PromptVersionResponse:
        return PromptVersionResponse(
            agent_type=AgentType(row["agent_type"]),
            version=row["version"],
            prompt=row["prompt"],
            parent_version=row["parent_version"],
            reflection=row["reflection"],
            average_scores=decode_json(row["average_scores"], default=None),
            status=PromptStatus(row["status"]),
            is_active=bool(row["is_active"]),
            selected_at=(
                datetime.fromisoformat(row["selected_at"])
                if row["selected_at"]
                else None
            ),
            activated_at=(
                datetime.fromisoformat(row["activated_at"])
                if row["activated_at"]
                else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _row_to_result(self, row: Any) -> OptimisationResultResponse:
        comparison = decode_json(row["comparison_results"])
        return OptimisationResultResponse(
            optimisation_id=int(row["id"]),
            job_id=row["job_id"],
            owner_id=row["owner_id"],
            agent_type=AgentType(row["agent_type"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            **comparison,
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
