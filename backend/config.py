from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    openai_judge_model: str
    sqlite_db_path: Path
    estimated_input_cost_per_1m_tokens: float
    estimated_output_cost_per_1m_tokens: float


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        openai_judge_model=os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")),
        sqlite_db_path=Path(os.getenv("SQLITE_DB_PATH", str(PROJECT_ROOT / "optimizer.sqlite3"))),
        estimated_input_cost_per_1m_tokens=float(os.getenv("ESTIMATED_INPUT_COST_PER_1M_TOKENS", "0.15")),
        estimated_output_cost_per_1m_tokens=float(os.getenv("ESTIMATED_OUTPUT_COST_PER_1M_TOKENS", "0.60")),
    )
