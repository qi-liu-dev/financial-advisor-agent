from __future__ import annotations

from datetime import datetime, timezone

from backend.database import get_connection
from backend.models.schemas import AdvisorMemoryResponse, AdvisorPreferences
from backend.security.crypto import decode_json, encode_json


class AdvisorMemoryRepository:
    def get_preferences(self, advisor_id: str) -> AdvisorPreferences:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT preferences FROM advisor_memory WHERE advisor_id = ?",
                (advisor_id,),
            ).fetchone()
        if row is None:
            return AdvisorPreferences()
        return AdvisorPreferences.model_validate(decode_json(row["preferences"]))

    def get_memory(
        self,
        advisor_id: str,
        *,
        create_if_missing: bool = True,
    ) -> AdvisorMemoryResponse | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM advisor_memory WHERE advisor_id = ?",
                (advisor_id,),
            ).fetchone()
        if row is None:
            if not create_if_missing:
                return None
            return self.save_preferences(
                advisor_id,
                AdvisorPreferences(),
                owner_id=advisor_id,
            )
        created_at = row["created_at"] or row["updated_at"]
        return AdvisorMemoryResponse(
            advisor_id=row["advisor_id"],
            preferences=AdvisorPreferences.model_validate(
                decode_json(row["preferences"])
            ),
            created_at=datetime.fromisoformat(created_at),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save_preferences(
        self,
        advisor_id: str,
        preferences: AdvisorPreferences,
        *,
        owner_id: str | None = None,
    ) -> AdvisorMemoryResponse:
        timestamp = datetime.now(timezone.utc)
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO advisor_memory (
                    advisor_id, owner_id, preferences, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(advisor_id) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    preferences = excluded.preferences,
                    updated_at = excluded.updated_at
                """,
                (
                    advisor_id,
                    owner_id or advisor_id,
                    encode_json(preferences.model_dump()),
                    timestamp.isoformat(),
                    timestamp.isoformat(),
                ),
            )
            row = conn.execute(
                "SELECT created_at, updated_at FROM advisor_memory WHERE advisor_id = ?",
                (advisor_id,),
            ).fetchone()
        return AdvisorMemoryResponse(
            advisor_id=advisor_id,
            preferences=preferences,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def delete_memory(self, advisor_id: str) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM advisor_memory WHERE advisor_id = ?",
                (advisor_id,),
            )
            return cursor.rowcount > 0
