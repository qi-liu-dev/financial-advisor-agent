from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _choice_env(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {choices}. Got: {value!r}")
    return value


def _float_env(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw = os.getenv(name)
    try:
        value = float(raw) if raw is not None else default
    except ValueError as exc:
        raise ValueError(f"{name} must be a number. Got: {raw!r}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}. Got: {value}")
    return value


def _int_env(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw is not None else default
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer. Got: {raw!r}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}. Got: {value}")
    return value


@dataclass(frozen=True)
class Settings:
    # Provider and authentication.
    llm_provider: str
    llm_auth_mode: str
    openai_api_key: str | None
    openai_base_url: str | None
    azure_openai_api_key: str | None
    azure_openai_base_url: str | None
    azure_openai_endpoint: str | None
    azure_openai_scope: str
    azure_client_id: str | None

    # On Azure, these values are deployment names.
    openai_model: str
    openai_judge_model: str

    # HTTP resilience and logging.
    llm_connect_timeout_seconds: float
    llm_read_timeout_seconds: float
    llm_write_timeout_seconds: float
    llm_pool_timeout_seconds: float
    llm_max_retries: int
    llm_log_level: str

    # Existing application settings.
    sqlite_db_path: Path
    estimated_input_cost_per_1m_tokens: float
    estimated_output_cost_per_1m_tokens: float


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
    judge_model = os.getenv("OPENAI_JUDGE_MODEL", model).strip()

    return Settings(
        llm_provider=_choice_env("LLM_PROVIDER", "openai", {"openai", "azure"}),
        llm_auth_mode=_choice_env(
            "LLM_AUTH_MODE",
            "api_key",
            {"api_key", "managed_identity"},
        ),
        openai_api_key=_optional_env("OPENAI_API_KEY"),
        openai_base_url=_optional_env("OPENAI_BASE_URL"),
        azure_openai_api_key=_optional_env("AZURE_OPENAI_API_KEY"),
        azure_openai_base_url=_optional_env("AZURE_OPENAI_BASE_URL"),
        azure_openai_endpoint=_optional_env("AZURE_OPENAI_ENDPOINT"),
        azure_openai_scope=os.getenv(
            "AZURE_OPENAI_SCOPE",
            "https://ai.azure.com/.default",
        ).strip(),
        azure_client_id=_optional_env("AZURE_CLIENT_ID"),
        openai_model=model,
        openai_judge_model=judge_model,
        llm_connect_timeout_seconds=_float_env(
            "LLM_CONNECT_TIMEOUT_SECONDS",
            5.0,
            minimum=0.1,
        ),
        llm_read_timeout_seconds=_float_env(
            "LLM_READ_TIMEOUT_SECONDS",
            90.0,
            minimum=0.1,
        ),
        llm_write_timeout_seconds=_float_env(
            "LLM_WRITE_TIMEOUT_SECONDS",
            30.0,
            minimum=0.1,
        ),
        llm_pool_timeout_seconds=_float_env(
            "LLM_POOL_TIMEOUT_SECONDS",
            10.0,
            minimum=0.1,
        ),
        llm_max_retries=_int_env("LLM_MAX_RETRIES", 2, minimum=0),
        llm_log_level=_choice_env(
            "LLM_LOG_LEVEL",
            "info",
            {"debug", "info", "warning", "error", "critical"},
        ).upper(),
        sqlite_db_path=Path(
            os.getenv("SQLITE_DB_PATH", str(PROJECT_ROOT / "optimizer.sqlite3"))
        ),
        estimated_input_cost_per_1m_tokens=_float_env(
            "ESTIMATED_INPUT_COST_PER_1M_TOKENS",
            0.15,
        ),
        estimated_output_cost_per_1m_tokens=_float_env(
            "ESTIMATED_OUTPUT_COST_PER_1M_TOKENS",
            0.60,
        ),
    )
