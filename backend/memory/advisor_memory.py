from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.database import get_connection
from backend.models.schemas import AdvisorPreferences


class AdvisorMemoryRepository:
    def get_preferences(self, advisor_id: str) -> AdvisorPreferences:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT preferences FROM advisor_memory WHERE advisor_id = ?",
                (advisor_id,),
            ).fetchone()
        if row is None:
            return AdvisorPreferences()
        return AdvisorPreferences.model_validate_json(row["preferences"])

    def save_preferences(self, advisor_id: str, preferences: AdvisorPreferences) -> AdvisorPreferences:
        timestamp = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO advisor_memory (advisor_id, preferences, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(advisor_id) DO UPDATE SET
                    preferences = excluded.preferences,
                    updated_at = excluded.updated_at
                """,
                (advisor_id, preferences.model_dump_json(), timestamp),
            )
        return preferences
