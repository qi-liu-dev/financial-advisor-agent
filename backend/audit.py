from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.database import get_connection
from backend.models.schemas import AuditEventResponse
from backend.security.crypto import decode_json, encode_json


class AuditRepository:
    def log(
        self,
        *,
        principal_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, str | int | float | bool | None] | None = None,
    ) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_events (
                    principal_id, action, resource_type, resource_id,
                    request_id, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    principal_id,
                    action,
                    resource_type,
                    resource_id,
                    request_id,
                    encode_json(metadata) if metadata is not None else None,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def list_events(
        self,
        *,
        page: int,
        page_size: int,
        principal_id: str | None = None,
    ) -> tuple[list[AuditEventResponse], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if principal_id:
            clauses.append("principal_id = ?")
            params.append(principal_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (page - 1) * page_size
        with get_connection() as conn:
            total = int(
                conn.execute(
                    f"SELECT COUNT(*) AS count FROM audit_events {where}",
                    tuple(params),
                ).fetchone()["count"]
            )
            rows = conn.execute(
                f"""
                SELECT * FROM audit_events
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, page_size, offset),
            ).fetchall()
        return [self._to_response(row) for row in rows], total

    def _to_response(self, row: Any) -> AuditEventResponse:
        return AuditEventResponse(
            id=int(row["id"]),
            principal_id=row["principal_id"],
            action=row["action"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            request_id=row["request_id"],
            metadata=decode_json(row["metadata"], default=None),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
