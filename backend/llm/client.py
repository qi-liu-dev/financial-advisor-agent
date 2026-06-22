from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Generic, Mapping, TypeVar
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import openai
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from backend.config import Settings, get_settings


ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)
logger = logging.getLogger("financial_advisor.llm")


class LLMError(RuntimeError):
    """Base class for safe, provider-neutral LLM errors."""


class LLMConfigurationError(LLMError):
    """Raised when the selected LLM provider is configured incorrectly."""


class LLMRequestError(LLMError):
    """Raised when a provider request fails before a usable response exists."""

    def __init__(
        self,
        *,
        operation: str,
        provider: str,
        client_request_id: str,
        provider_request_id: str | None = None,
        status_code: int | None = None,
        error_type: str,
    ) -> None:
        self.operation = operation
        self.provider = provider
        self.client_request_id = client_request_id
        self.provider_request_id = provider_request_id
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(
            "LLM request failed "
            f"(provider={provider}, operation={operation}, error_type={error_type}, "
            f"status_code={status_code or 'n/a'}, "
            f"provider_request_id={provider_request_id or 'n/a'}, "
            f"client_request_id={client_request_id})."
        )


class LLMResponseError(LLMError):
    """Raised when the provider returns unusable structured output."""

    def __init__(
        self,
        *,
        operation: str,
        provider: str,
        client_request_id: str,
        provider_request_id: str | None,
        response_model: str,
        reason: str,
    ) -> None:
        self.operation = operation
        self.provider = provider
        self.client_request_id = client_request_id
        self.provider_request_id = provider_request_id
        self.response_model = response_model
        self.reason = reason
        super().__init__(
            "LLM returned an invalid structured response "
            f"(provider={provider}, operation={operation}, response_model={response_model}, "
            f"reason={reason}, provider_request_id={provider_request_id or 'n/a'}, "
            f"client_request_id={client_request_id})."
        )


@dataclass(frozen=True, slots=True)
class StructuredChatResult(Generic[ResponseModelT]):
    output: ResponseModelT
    model: str
    token_usage: dict[str, Any] | None
    latency_ms: float
    provider_request_id: str | None
    client_request_id: str


class LLMClient:
    """Provider-neutral synchronous gateway around the OpenAI Python SDK.

    Azure OpenAI's v1 API uses the same ``OpenAI`` client as public OpenAI.
    Business modules therefore only supply prompts, models, and schemas; this
    class owns provider selection, authentication, retry/timeout policy,
    request correlation, and metadata-only logging.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        sdk_client: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = self.settings.llm_provider
        self.auth_mode = self.settings.llm_auth_mode
        self._azure_credential: Any | None = None
        logger.setLevel(getattr(logging, self.settings.llm_log_level, logging.INFO))
        self._validate_configuration()
        self._sdk_client = sdk_client or self._build_sdk_client()

    def structured_chat(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        response_model: type[ResponseModelT],
        temperature: float,
        operation: str,
        log_context: Mapping[str, str] | None = None,
    ) -> StructuredChatResult[ResponseModelT]:
        """Call a JSON-schema constrained chat completion and validate it.

        Prompts, financial inputs, and model outputs are intentionally never
        logged. Only operational metadata, token counts, latency, and IDs are
        emitted.
        """

        client_request_id = str(uuid4())
        started = time.perf_counter()
        context = _format_log_context(log_context)

        logger.info(
            "llm_call_started client_request_id=%s operation=%s provider=%s "
            "auth_mode=%s model=%s max_retries=%s%s",
            client_request_id,
            operation,
            self.provider,
            self.auth_mode,
            model,
            self.settings.llm_max_retries,
            context,
        )

        try:
            raw_response = self._sdk_client.chat.completions.with_raw_response.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "schema": response_model.model_json_schema(),
                        # Existing schemas contain defaults, so retain the
                        # repository's non-strict structured-output behaviour.
                        "strict": False,
                    },
                },
                extra_headers=self._correlation_headers(client_request_id),
            )
            response = raw_response.parse()
        except openai.APITimeoutError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            logger.warning(
                "llm_call_failed client_request_id=%s operation=%s provider=%s "
                "model=%s error_type=%s latency_ms=%.2f%s",
                client_request_id,
                operation,
                self.provider,
                model,
                type(exc).__name__,
                latency_ms,
                context,
            )
            raise LLMRequestError(
                operation=operation,
                provider=self.provider,
                client_request_id=client_request_id,
                error_type=type(exc).__name__,
            ) from exc
        except openai.APIStatusError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            provider_request_id = _extract_error_request_id(exc)
            logger.warning(
                "llm_call_failed client_request_id=%s provider_request_id=%s "
                "operation=%s provider=%s model=%s error_type=%s "
                "status_code=%s latency_ms=%.2f%s",
                client_request_id,
                provider_request_id or "unknown",
                operation,
                self.provider,
                model,
                type(exc).__name__,
                exc.status_code,
                latency_ms,
                context,
            )
            raise LLMRequestError(
                operation=operation,
                provider=self.provider,
                client_request_id=client_request_id,
                provider_request_id=provider_request_id,
                status_code=exc.status_code,
                error_type=type(exc).__name__,
            ) from exc
        except openai.APIConnectionError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            logger.warning(
                "llm_call_failed client_request_id=%s operation=%s provider=%s "
                "model=%s error_type=%s latency_ms=%.2f%s",
                client_request_id,
                operation,
                self.provider,
                model,
                type(exc).__name__,
                latency_ms,
                context,
            )
            raise LLMRequestError(
                operation=operation,
                provider=self.provider,
                client_request_id=client_request_id,
                error_type=type(exc).__name__,
            ) from exc
        except openai.APIError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            logger.warning(
                "llm_call_failed client_request_id=%s operation=%s provider=%s "
                "model=%s error_type=%s latency_ms=%.2f%s",
                client_request_id,
                operation,
                self.provider,
                model,
                type(exc).__name__,
                latency_ms,
                context,
            )
            raise LLMRequestError(
                operation=operation,
                provider=self.provider,
                client_request_id=client_request_id,
                error_type=type(exc).__name__,
            ) from exc
        except Exception as exc:
            # Azure Identity can raise its own authentication exception before
            # an HTTP response exists. Log the type but never the credential.
            latency_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "llm_call_failed client_request_id=%s operation=%s provider=%s "
                "model=%s error_type=%s latency_ms=%.2f%s",
                client_request_id,
                operation,
                self.provider,
                model,
                type(exc).__name__,
                latency_ms,
                context,
            )
            raise LLMRequestError(
                operation=operation,
                provider=self.provider,
                client_request_id=client_request_id,
                error_type=type(exc).__name__,
            ) from exc

        latency_ms = (time.perf_counter() - started) * 1000
        provider_request_id = _extract_request_id(
            response=response,
            headers=getattr(raw_response, "headers", None),
        )
        try:
            output = self._parse_response(
                response=response,
                response_model=response_model,
                operation=operation,
                client_request_id=client_request_id,
                provider_request_id=provider_request_id,
            )
        except LLMResponseError as exc:
            logger.warning(
                "llm_response_invalid client_request_id=%s provider_request_id=%s "
                "operation=%s provider=%s model=%s reason=%s latency_ms=%.2f%s",
                client_request_id,
                provider_request_id or "unknown",
                operation,
                self.provider,
                model,
                exc.reason,
                latency_ms,
                context,
            )
            raise
        token_usage = _dump_usage(getattr(response, "usage", None))

        logger.info(
            "llm_call_succeeded client_request_id=%s provider_request_id=%s "
            "operation=%s provider=%s model=%s latency_ms=%.2f "
            "input_tokens=%s output_tokens=%s%s",
            client_request_id,
            provider_request_id or "unknown",
            operation,
            self.provider,
            model,
            latency_ms,
            _input_tokens(token_usage),
            _output_tokens(token_usage),
            context,
        )
        return StructuredChatResult(
            output=output,
            model=model,
            token_usage=token_usage,
            latency_ms=latency_ms,
            provider_request_id=provider_request_id,
            client_request_id=client_request_id,
        )

    def close(self) -> None:
        close_client = getattr(self._sdk_client, "close", None)
        if callable(close_client):
            close_client()

        close_credential = getattr(self._azure_credential, "close", None)
        if callable(close_credential):
            close_credential()

    def _validate_configuration(self) -> None:
        if not self.settings.openai_model:
            raise LLMConfigurationError("OPENAI_MODEL must not be empty.")
        if not self.settings.openai_judge_model:
            raise LLMConfigurationError("OPENAI_JUDGE_MODEL must not be empty.")

        if self.provider == "openai":
            if self.auth_mode != "api_key":
                raise LLMConfigurationError(
                    "LLM_PROVIDER=openai requires LLM_AUTH_MODE=api_key."
                )
            if not self.settings.openai_api_key:
                raise LLMConfigurationError(
                    "LLM_PROVIDER=openai requires OPENAI_API_KEY."
                )
            return

        if self.provider != "azure":
            raise LLMConfigurationError(
                "LLM_PROVIDER must be either openai or azure."
            )

        if not (
            self.settings.azure_openai_base_url
            or self.settings.azure_openai_endpoint
        ):
            raise LLMConfigurationError(
                "LLM_PROVIDER=azure requires AZURE_OPENAI_BASE_URL or "
                "AZURE_OPENAI_ENDPOINT."
            )
        if self.auth_mode == "api_key" and not self.settings.azure_openai_api_key:
            raise LLMConfigurationError(
                "Azure API-key authentication requires AZURE_OPENAI_API_KEY."
            )
        if self.auth_mode not in {"api_key", "managed_identity"}:
            raise LLMConfigurationError(
                "Azure requires LLM_AUTH_MODE=api_key or managed_identity."
            )

    def _build_sdk_client(self) -> OpenAI:
        timeout = httpx.Timeout(
            connect=self.settings.llm_connect_timeout_seconds,
            read=self.settings.llm_read_timeout_seconds,
            write=self.settings.llm_write_timeout_seconds,
            pool=self.settings.llm_pool_timeout_seconds,
        )
        common_options: dict[str, Any] = {
            "timeout": timeout,
            "max_retries": self.settings.llm_max_retries,
        }

        if self.provider == "openai":
            if self.settings.openai_base_url:
                common_options["base_url"] = self.settings.openai_base_url
            logger.info(
                "llm_client_created provider=openai auth_mode=api_key "
                "endpoint_host=%s",
                _endpoint_host(
                    self.settings.openai_base_url or "https://api.openai.com/v1"
                ),
            )
            return OpenAI(
                api_key=self.settings.openai_api_key,
                **common_options,
            )

        base_url = _azure_v1_base_url(self.settings)
        if self.auth_mode == "api_key":
            credential: str | Any = self.settings.azure_openai_api_key
        else:
            try:
                from azure.identity import (
                    DefaultAzureCredential,
                    get_bearer_token_provider,
                )
            except ImportError as exc:
                raise LLMConfigurationError(
                    "Azure Managed Identity requires the azure-identity package."
                ) from exc

            credential_options: dict[str, Any] = {}
            if self.settings.azure_client_id:
                credential_options["managed_identity_client_id"] = (
                    self.settings.azure_client_id
                )
            self._azure_credential = DefaultAzureCredential(**credential_options)
            credential = get_bearer_token_provider(
                self._azure_credential,
                self.settings.azure_openai_scope,
            )

        logger.info(
            "llm_client_created provider=azure auth_mode=%s endpoint_host=%s",
            self.auth_mode,
            _endpoint_host(base_url),
        )
        return OpenAI(
            api_key=credential,
            base_url=base_url,
            **common_options,
        )

    def _correlation_headers(self, client_request_id: str) -> dict[str, str]:
        if self.provider == "azure":
            return {"x-ms-client-request-id": client_request_id}
        return {"X-Client-Request-Id": client_request_id}

    def _parse_response(
        self,
        *,
        response: Any,
        response_model: type[ResponseModelT],
        operation: str,
        client_request_id: str,
        provider_request_id: str | None,
    ) -> ResponseModelT:
        choices = getattr(response, "choices", None)
        if not choices:
            raise LLMResponseError(
                operation=operation,
                provider=self.provider,
                client_request_id=client_request_id,
                provider_request_id=provider_request_id,
                response_model=response_model.__name__,
                reason="missing_choices",
            )

        message = choices[0].message
        if getattr(message, "refusal", None):
            raise LLMResponseError(
                operation=operation,
                provider=self.provider,
                client_request_id=client_request_id,
                provider_request_id=provider_request_id,
                response_model=response_model.__name__,
                reason="model_refusal",
            )

        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError(
                operation=operation,
                provider=self.provider,
                client_request_id=client_request_id,
                provider_request_id=provider_request_id,
                response_model=response_model.__name__,
                reason="empty_content",
            )

        try:
            return response_model.model_validate_json(content)
        except (ValidationError, ValueError, json.JSONDecodeError):
            try:
                decoded = _extract_first_json_value(content)
                return response_model.model_validate(decoded)
            except (ValidationError, ValueError, json.JSONDecodeError) as fallback_error:
                raise LLMResponseError(
                    operation=operation,
                    provider=self.provider,
                    client_request_id=client_request_id,
                    provider_request_id=provider_request_id,
                    response_model=response_model.__name__,
                    reason="schema_validation_failed",
                ) from fallback_error


def is_llm_configured(settings: Settings | None = None) -> bool:
    """Return whether static configuration is sufficient to attempt a call."""

    config = settings or get_settings()
    if config.llm_provider == "openai":
        return config.llm_auth_mode == "api_key" and bool(config.openai_api_key)

    if config.llm_provider == "azure":
        has_endpoint = bool(
            config.azure_openai_base_url or config.azure_openai_endpoint
        )
        if config.llm_auth_mode == "api_key":
            return has_endpoint and bool(config.azure_openai_api_key)
        if config.llm_auth_mode == "managed_identity":
            # Actual token/RBAC access is verified when the first call occurs.
            return has_endpoint

    return False


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Return one process-wide client to reuse HTTP connections and tokens."""

    return LLMClient()


def close_llm_client() -> None:
    """Close cached HTTP/Azure resources during application shutdown."""

    if get_llm_client.cache_info().currsize:
        try:
            get_llm_client().close()
        finally:
            get_llm_client.cache_clear()


def _azure_v1_base_url(settings: Settings) -> str:
    raw = settings.azure_openai_base_url or settings.azure_openai_endpoint
    if not raw:
        raise LLMConfigurationError(
            "AZURE_OPENAI_BASE_URL or AZURE_OPENAI_ENDPOINT is required."
        )

    base_url = raw.strip().rstrip("/")
    if not base_url.startswith(("https://", "http://")):
        raise LLMConfigurationError(
            "Azure OpenAI endpoint must start with http:// or https://."
        )

    lowered = base_url.lower()
    if lowered.endswith("/openai/v1"):
        return f"{base_url}/"
    if lowered.endswith("/openai"):
        return f"{base_url}/v1/"
    if "/openai/" not in lowered:
        return f"{base_url}/openai/v1/"

    raise LLMConfigurationError(
        "Azure OpenAI base URL must be the resource endpoint or end with "
        "/openai/v1/."
    )


def _extract_request_id(*, response: Any, headers: Any | None) -> str | None:
    response_request_id = getattr(response, "_request_id", None)
    if response_request_id:
        return str(response_request_id)
    return _request_id_from_headers(headers)


def _extract_error_request_id(exc: openai.APIStatusError) -> str | None:
    request_id = getattr(exc, "request_id", None)
    if request_id:
        return str(request_id)
    response = getattr(exc, "response", None)
    return _request_id_from_headers(getattr(response, "headers", None))


def _request_id_from_headers(headers: Any | None) -> str | None:
    if headers is None:
        return None
    for name in ("x-request-id", "apim-request-id", "x-ms-request-id"):
        try:
            value = headers.get(name)
        except AttributeError:
            return None
        if value:
            return str(value)
    return None


def _dump_usage(usage: Any | None) -> dict[str, Any] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump(exclude_none=True)
    if hasattr(usage, "to_dict"):
        return usage.to_dict()
    if isinstance(usage, dict):
        return dict(usage)
    return None


def _input_tokens(usage: dict[str, Any] | None) -> int | str:
    if not usage:
        return "unknown"
    return usage.get("prompt_tokens", usage.get("input_tokens", "unknown"))


def _output_tokens(usage: dict[str, Any] | None) -> int | str:
    if not usage:
        return "unknown"
    return usage.get(
        "completion_tokens",
        usage.get("output_tokens", "unknown"),
    )


def _extract_first_json_value(content: str) -> Any:
    first_brace = content.find("{")
    if first_brace < 0:
        raise ValueError("No JSON object found in model response.")
    decoded, _ = json.JSONDecoder().raw_decode(content[first_brace:])
    return decoded


def _format_log_context(context: Mapping[str, str] | None) -> str:
    if not context:
        return ""
    parts: list[str] = []
    for key, value in sorted(context.items()):
        safe_key = "".join(char for char in key if char.isalnum() or char in "_-")
        safe_value = str(value).replace(" ", "_").replace("\n", "_")[:120]
        if safe_key:
            parts.append(f"{safe_key}={safe_value}")
    return f" {' '.join(parts)}" if parts else ""


def _endpoint_host(endpoint: str) -> str:
    return urlparse(endpoint).netloc or "custom"
