from __future__ import annotations

import logging
import sqlite3
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from typing import Callable
from uuid import uuid4

from backend.database import get_connection
from backend.llm import LLMConfigurationError, LLMRequestError, LLMResponseError
from backend.models.schemas import (
    AgentType,
    OptimisationJobResponse,
    OptimisationJobStatus,
    OptimisationRequest,
)
from backend.optimisation.gepa_loop import GEPAInspiredOptimiser
from backend.security.crypto import decode_json, encode_json


logger = logging.getLogger("financial_advisor.optimisation_jobs")


class OptimisationJobConflict(RuntimeError):
    pass


class OptimisationJobStore:
    def create_job(
        self,
        *,
        owner_id: str,
        agent_type: AgentType,
        request: OptimisationRequest,
    ) -> OptimisationJobResponse:
        job_id = str(uuid4())
        created_at = datetime.now(timezone.utc)
        try:
            with get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """
                    INSERT INTO optimisation_jobs (
                        job_id, owner_id, agent_type, status, progress,
                        request_json, created_at
                    ) VALUES (?, ?, ?, 'queued', 0, ?, ?)
                    """,
                    (
                        job_id,
                        owner_id,
                        agent_type.value,
                        encode_json(request.model_dump(mode="json")),
                        created_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise OptimisationJobConflict(
                "An optimisation job for this owner and agent is already queued or running."
            ) from exc
        result = self.get_job(job_id)
        if result is None:
            raise RuntimeError("Optimisation job was not persisted.")
        return result

    def get_job(self, job_id: str) -> OptimisationJobResponse | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM optimisation_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return self._row_to_response(row) if row else None

    def list_jobs(
        self,
        *,
        page: int,
        page_size: int,
        owner_id: str | None = None,
        status: OptimisationJobStatus | None = None,
    ) -> tuple[list[OptimisationJobResponse], int]:
        clauses: list[str] = []
        params: list[object] = []
        if owner_id:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        if status:
            clauses.append("status = ?")
            params.append(status.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size
        with get_connection() as conn:
            total = int(
                conn.execute(
                    f"SELECT COUNT(*) AS count FROM optimisation_jobs {where}",
                    tuple(params),
                ).fetchone()["count"]
            )
            rows = conn.execute(
                f"""
                SELECT * FROM optimisation_jobs
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, page_size, offset),
            ).fetchall()
        return [self._row_to_response(row) for row in rows], total

    def mark_running(self, job_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE optimisation_jobs
                SET status = 'running', progress = 0.01, started_at = ?
                WHERE job_id = ? AND status = 'queued'
                """,
                (_utc_now(), job_id),
            )

    def update_progress(self, job_id: str, progress: float) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE optimisation_jobs
                SET progress = ?
                WHERE job_id = ? AND status = 'running'
                """,
                (min(0.99, max(0.01, progress)), job_id),
            )

    def mark_completed(self, job_id: str, result_id: int) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE optimisation_jobs
                SET status = 'completed', progress = 1, result_id = ?, completed_at = ?
                WHERE job_id = ?
                """,
                (result_id, _utc_now(), job_id),
            )

    def mark_failed(self, job_id: str, *, code: str, message: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE optimisation_jobs
                SET status = 'failed', progress = 1, error_code = ?,
                    error_message = ?, completed_at = ?
                WHERE job_id = ?
                """,
                (code, message, _utc_now(), job_id),
            )

    def fail_orphaned_jobs(self) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE optimisation_jobs
                SET status = 'failed', progress = 1,
                    error_code = 'worker_restarted',
                    error_message = 'The local worker restarted before this job completed.',
                    completed_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (_utc_now(),),
            )
            return max(0, cursor.rowcount)

    def _row_to_response(self, row: object) -> OptimisationJobResponse:
        return OptimisationJobResponse(
            job_id=row["job_id"],
            owner_id=row["owner_id"],
            agent_type=AgentType(row["agent_type"]),
            status=OptimisationJobStatus(row["status"]),
            progress=float(row["progress"]),
            request=OptimisationRequest.model_validate(
                decode_json(row["request_json"])
            ),
            result_id=row["result_id"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=(
                datetime.fromisoformat(row["started_at"])
                if row["started_at"]
                else None
            ),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
        )


class OptimisationJobManager:
    def __init__(
        self,
        *,
        max_workers: int,
        optimiser_factory: Callable[[], GEPAInspiredOptimiser] = GEPAInspiredOptimiser,
        store: OptimisationJobStore | None = None,
    ) -> None:
        self.store = store or OptimisationJobStore()
        self.optimiser_factory = optimiser_factory
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="prompt-optimiser",
        )
        self._futures: dict[str, Future[None]] = {}
        self._lock = Lock()

    def submit(
        self,
        *,
        owner_id: str,
        agent_type: AgentType,
        request: OptimisationRequest,
    ) -> OptimisationJobResponse:
        job = self.store.create_job(
            owner_id=owner_id,
            agent_type=agent_type,
            request=request,
        )
        future = self.executor.submit(
            self._execute,
            job.job_id,
            owner_id,
            agent_type,
            request,
        )
        with self._lock:
            self._futures[job.job_id] = future
        future.add_done_callback(lambda _: self._forget(job.job_id))
        return job

    def shutdown(self, *, wait: bool = True) -> None:
        self.executor.shutdown(wait=wait, cancel_futures=False)

    def _execute(
        self,
        job_id: str,
        owner_id: str,
        agent_type: AgentType,
        request: OptimisationRequest,
    ) -> None:
        self.store.mark_running(job_id)
        try:
            optimiser = self.optimiser_factory()
            result = optimiser.optimise(
                agent_type=agent_type,
                advisor_id=request.advisor_id or owner_id,
                owner_id=owner_id,
                job_id=job_id,
                max_variants=request.max_variants,
                benchmark_limit=request.benchmark_limit,
                repetitions=request.repetitions,
                progress_callback=lambda value: self.store.update_progress(
                    job_id,
                    value,
                ),
            )
            self.store.mark_completed(job_id, result.optimisation_id)
        except LLMConfigurationError:
            logger.exception("optimisation_job_configuration_failed job_id=%s", job_id)
            self.store.mark_failed(
                job_id,
                code="llm_configuration_error",
                message="The LLM provider or judge policy is not configured correctly.",
            )
        except (LLMRequestError, LLMResponseError):
            logger.exception("optimisation_job_llm_failed job_id=%s", job_id)
            self.store.mark_failed(
                job_id,
                code="llm_upstream_error",
                message="The LLM provider failed while running the optimisation.",
            )
        except Exception:
            logger.exception("optimisation_job_failed job_id=%s", job_id)
            self.store.mark_failed(
                job_id,
                code="optimisation_failed",
                message="Prompt optimisation failed unexpectedly.",
            )

    def _forget(self, job_id: str) -> None:
        with self._lock:
            self._futures.pop(job_id, None)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
