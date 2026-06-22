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


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean. Got: {raw!r}")


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values


def _api_prefix(value: str) -> str:
    value = value.strip()
    if not value.startswith("/"):
        value = f"/{value}"
    return value.rstrip("/") or "/api/v1"


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

    # API and browser integration.
    api_prefix: str = "/api/v1"
    cors_allowed_origins: tuple[str, ...] = ("http://localhost:4200",)
    cors_allow_credentials: bool = False

    # Authentication. ``azure_easy_auth`` trusts headers injected by Azure
    # Container Apps/App Service authentication and must only be enabled behind
    # that trusted ingress boundary.
    auth_mode: str = "disabled"
    api_keys_json: str | None = None
    dev_principal_id: str = "demo-advisor"
    dev_principal_roles: tuple[str, ...] = ("admin", "advisor")

    # In-process rate limiting. For multi-replica production deployments use a
    # shared gateway/store (for example API Management or Redis) instead.
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    # SQLite, privacy, and retention.
    database_busy_timeout_ms: int = 30_000
    data_encryption_key: str | None = None
    data_retention_days: int = 90

    # Evaluation and optimisation policy.
    require_distinct_judge_model: bool = False
    require_llm_for_readiness: bool = False
    optimisation_worker_count: int = 2
    optimisation_default_repetitions: int = 2
    optimisation_max_repetitions: int = 5
    optimisation_minimum_quality_delta: float = 0.05
    optimisation_safety_tolerance: float = 0.0
    optimisation_latency_tolerance_ratio: float = 1.20
    optimisation_cost_tolerance_ratio: float = 1.10


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
        api_prefix=_api_prefix(os.getenv("API_PREFIX", "/api/v1")),
        cors_allowed_origins=_csv_env(
            "CORS_ALLOWED_ORIGINS",
            ("http://localhost:4200",),
        ),
        cors_allow_credentials=_bool_env("CORS_ALLOW_CREDENTIALS", False),
        auth_mode=_choice_env(
            "AUTH_MODE",
            "disabled",
            {"disabled", "api_key", "azure_easy_auth"},
        ),
        api_keys_json=_optional_env("API_KEYS_JSON"),
        dev_principal_id=os.getenv("DEV_PRINCIPAL_ID", "demo-advisor").strip()
        or "demo-advisor",
        dev_principal_roles=_csv_env(
            "DEV_PRINCIPAL_ROLES",
            ("admin", "advisor"),
        ),
        rate_limit_enabled=_bool_env("RATE_LIMIT_ENABLED", True),
        rate_limit_requests=_int_env("RATE_LIMIT_REQUESTS", 120, minimum=1),
        rate_limit_window_seconds=_int_env(
            "RATE_LIMIT_WINDOW_SECONDS",
            60,
            minimum=1,
        ),
        database_busy_timeout_ms=_int_env(
            "DATABASE_BUSY_TIMEOUT_MS",
            30_000,
            minimum=1,
        ),
        data_encryption_key=_optional_env("DATA_ENCRYPTION_KEY"),
        data_retention_days=_int_env("DATA_RETENTION_DAYS", 90, minimum=0),
        require_distinct_judge_model=_bool_env(
            "REQUIRE_DISTINCT_JUDGE_MODEL",
            False,
        ),
        require_llm_for_readiness=_bool_env(
            "REQUIRE_LLM_FOR_READINESS",
            False,
        ),
        optimisation_worker_count=_int_env(
            "OPTIMISATION_WORKER_COUNT",
            2,
            minimum=1,
        ),
        optimisation_default_repetitions=_int_env(
            "OPTIMISATION_DEFAULT_REPETITIONS",
            2,
            minimum=1,
        ),
        optimisation_max_repetitions=_int_env(
            "OPTIMISATION_MAX_REPETITIONS",
            5,
            minimum=1,
        ),
        optimisation_minimum_quality_delta=_float_env(
            "OPTIMISATION_MINIMUM_QUALITY_DELTA",
            0.05,
            minimum=0.0,
        ),
        optimisation_safety_tolerance=_float_env(
            "OPTIMISATION_SAFETY_TOLERANCE",
            0.0,
            minimum=0.0,
        ),
        optimisation_latency_tolerance_ratio=_float_env(
            "OPTIMISATION_LATENCY_TOLERANCE_RATIO",
            1.20,
            minimum=1.0,
        ),
        optimisation_cost_tolerance_ratio=_float_env(
            "OPTIMISATION_COST_TOLERANCE_RATIO",
            1.10,
            minimum=1.0,
        ),
    )
