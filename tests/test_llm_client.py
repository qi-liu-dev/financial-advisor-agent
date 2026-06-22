from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
from openai import OpenAI
from pydantic import BaseModel

from backend.config import Settings
from backend.llm.client import (
    LLMClient,
    LLMConfigurationError,
    LLMResponseError,
    _azure_v1_base_url,
    is_llm_configured,
)


class ExampleOutput(BaseModel):
    answer: str


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "llm_provider": "openai",
        "llm_auth_mode": "api_key",
        "openai_api_key": "test-openai-key",
        "openai_base_url": None,
        "azure_openai_api_key": None,
        "azure_openai_base_url": None,
        "azure_openai_endpoint": None,
        "azure_openai_scope": "https://ai.azure.com/.default",
        "azure_client_id": None,
        "openai_model": "test-agent-model",
        "openai_judge_model": "test-judge-model",
        "llm_connect_timeout_seconds": 1.0,
        "llm_read_timeout_seconds": 2.0,
        "llm_write_timeout_seconds": 3.0,
        "llm_pool_timeout_seconds": 4.0,
        "llm_max_retries": 0,
        "llm_log_level": "INFO",
        "sqlite_db_path": Path("test.sqlite3"),
        "estimated_input_cost_per_1m_tokens": 0.15,
        "estimated_output_cost_per_1m_tokens": 0.60,
    }
    values.update(overrides)
    return Settings(**values)


def _chat_completion(content: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1_700_000_000,
        "model": "test-agent-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "refusal": None,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
        },
    }


def _sdk_client(handler: Any, *, max_retries: int = 0) -> OpenAI:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return OpenAI(
        api_key="test-sdk-key",
        base_url="https://provider.example/v1/",
        http_client=http_client,
        max_retries=max_retries,
    )


def test_openai_call_returns_structured_output_and_correlation_ids() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["client_request_id"] = request.headers.get("x-client-request-id")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"x-request-id": "req_provider_123"},
            json=_chat_completion('{"answer":"grounded"}'),
        )

    gateway = LLMClient(
        settings=_settings(),
        sdk_client=_sdk_client(handler),
    )
    result = gateway.structured_chat(
        model="test-agent-model",
        system_prompt="Do not log this system prompt.",
        user_message="Do not log this synthetic financial payload.",
        response_model=ExampleOutput,
        temperature=0.0,
        operation="test.structured_chat",
        log_context={"agent_type": "client_summary"},
    )

    assert result.output == ExampleOutput(answer="grounded")
    assert result.provider_request_id == "req_provider_123"
    assert result.client_request_id == captured["client_request_id"]
    UUID(result.client_request_id)
    assert result.token_usage == {
        "completion_tokens": 7,
        "prompt_tokens": 11,
        "total_tokens": 18,
    }
    assert captured["body"]["response_format"]["type"] == "json_schema"
    assert captured["body"]["response_format"]["json_schema"]["strict"] is False


def test_azure_call_sends_azure_client_request_id_header() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["azure_client_request_id"] = request.headers.get(
            "x-ms-client-request-id"
        )
        captured["openai_client_request_id"] = request.headers.get(
            "x-client-request-id"
        )
        return httpx.Response(
            200,
            headers={"apim-request-id": "azure-provider-request-456"},
            json=_chat_completion('{"answer":"azure"}'),
        )

    gateway = LLMClient(
        settings=_settings(
            llm_provider="azure",
            azure_openai_api_key="test-azure-key",
            azure_openai_endpoint="https://resource.openai.azure.com",
        ),
        sdk_client=_sdk_client(handler),
    )
    result = gateway.structured_chat(
        model="azure-deployment-name",
        system_prompt="system",
        user_message="user",
        response_model=ExampleOutput,
        temperature=0.0,
        operation="test.azure",
    )

    assert captured["azure_client_request_id"] == result.client_request_id
    assert captured["openai_client_request_id"] is None
    assert result.provider_request_id == "azure-provider-request-456"


def test_sdk_retry_reuses_the_same_client_request_id() -> None:
    call_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        call_headers.append(request.headers.get("x-client-request-id"))
        if len(call_headers) == 1:
            return httpx.Response(
                429,
                headers={"x-request-id": "req_rate_limited"},
                json={
                    "error": {
                        "message": "Synthetic rate limit",
                        "type": "rate_limit_error",
                        "param": None,
                        "code": "rate_limit",
                    }
                },
            )
        return httpx.Response(
            200,
            headers={"x-request-id": "req_after_retry"},
            json=_chat_completion('{"answer":"retried"}'),
        )

    gateway = LLMClient(
        settings=_settings(llm_max_retries=1),
        sdk_client=_sdk_client(handler, max_retries=1),
    )
    result = gateway.structured_chat(
        model="test-agent-model",
        system_prompt="system",
        user_message="user",
        response_model=ExampleOutput,
        temperature=0.0,
        operation="test.retry",
    )

    assert len(call_headers) == 2
    assert call_headers[0] == call_headers[1] == result.client_request_id
    assert result.provider_request_id == "req_after_retry"


def test_invalid_structured_output_keeps_provider_request_id() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"x-request-id": "req_invalid_schema"},
            json=_chat_completion("{}"),
        )

    gateway = LLMClient(
        settings=_settings(),
        sdk_client=_sdk_client(handler),
    )

    with pytest.raises(LLMResponseError) as captured:
        gateway.structured_chat(
            model="test-agent-model",
            system_prompt="system",
            user_message="user",
            response_model=ExampleOutput,
            temperature=0.0,
            operation="test.invalid_schema",
        )

    assert captured.value.provider_request_id == "req_invalid_schema"
    assert captured.value.reason == "schema_validation_failed"


def test_configuration_and_azure_endpoint_helpers() -> None:
    managed_identity = _settings(
        llm_provider="azure",
        llm_auth_mode="managed_identity",
        openai_api_key=None,
        azure_openai_endpoint="https://resource.openai.azure.com/",
    )
    assert is_llm_configured(managed_identity) is True
    assert (
        _azure_v1_base_url(managed_identity)
        == "https://resource.openai.azure.com/openai/v1/"
    )

    full_url = _settings(
        llm_provider="azure",
        azure_openai_api_key="key",
        azure_openai_base_url=(
            "https://resource.services.ai.azure.com/openai/v1/"
        ),
    )
    assert (
        _azure_v1_base_url(full_url)
        == "https://resource.services.ai.azure.com/openai/v1/"
    )

    invalid = _settings(llm_auth_mode="managed_identity")
    with pytest.raises(LLMConfigurationError):
        LLMClient(settings=invalid, sdk_client=object())


def test_client_constructor_receives_timeout_and_retry_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeSDKClient:
        def close(self) -> None:
            return None

    def fake_openai(**kwargs: Any) -> FakeSDKClient:
        captured.update(kwargs)
        return FakeSDKClient()

    monkeypatch.setattr("backend.llm.client.OpenAI", fake_openai)
    gateway = LLMClient(
        settings=_settings(
            llm_connect_timeout_seconds=1.5,
            llm_read_timeout_seconds=12.0,
            llm_write_timeout_seconds=4.0,
            llm_pool_timeout_seconds=2.5,
            llm_max_retries=4,
        )
    )

    timeout = captured["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 1.5
    assert timeout.read == 12.0
    assert timeout.write == 4.0
    assert timeout.pool == 2.5
    assert captured["max_retries"] == 4
    gateway.close()


def test_managed_identity_builds_token_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import azure.identity

    captured: dict[str, Any] = {}

    class FakeCredential:
        def __init__(self, **kwargs: Any) -> None:
            captured["credential_kwargs"] = kwargs

        def close(self) -> None:
            captured["credential_closed"] = True

    def fake_token_provider(credential: Any, scope: str) -> Any:
        captured["credential"] = credential
        captured["scope"] = scope

        def token_provider() -> str:
            return "fake-token"

        return token_provider

    class FakeSDKClient:
        def close(self) -> None:
            captured["sdk_closed"] = True

    def fake_openai(**kwargs: Any) -> FakeSDKClient:
        captured["openai_kwargs"] = kwargs
        return FakeSDKClient()

    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", FakeCredential)
    monkeypatch.setattr(
        azure.identity,
        "get_bearer_token_provider",
        fake_token_provider,
    )
    monkeypatch.setattr("backend.llm.client.OpenAI", fake_openai)

    gateway = LLMClient(
        settings=_settings(
            llm_provider="azure",
            llm_auth_mode="managed_identity",
            openai_api_key=None,
            azure_openai_endpoint="https://resource.openai.azure.com",
            azure_client_id="user-assigned-client-id",
        )
    )

    assert captured["credential_kwargs"] == {
        "managed_identity_client_id": "user-assigned-client-id"
    }
    assert captured["scope"] == "https://ai.azure.com/.default"
    assert callable(captured["openai_kwargs"]["api_key"])
    assert (
        captured["openai_kwargs"]["base_url"]
        == "https://resource.openai.azure.com/openai/v1/"
    )
    gateway.close()
    assert captured["sdk_closed"] is True
    assert captured["credential_closed"] is True
