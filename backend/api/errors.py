from __future__ import annotations

from fastapi import HTTPException

from backend.llm import (
    LLMConfigurationError,
    LLMError,
    LLMRequestError,
    LLMResponseError,
)


def llm_http_exception(error: LLMError) -> HTTPException:
    if isinstance(error, LLMConfigurationError):
        return HTTPException(
            status_code=503,
            detail={
                "code": "llm_configuration_error",
                "message": "The LLM provider or judge policy is not configured correctly.",
            },
        )
    if isinstance(error, LLMRequestError):
        return HTTPException(
            status_code=502,
            detail={
                "code": "llm_upstream_error",
                "message": "The LLM provider request failed.",
                "client_request_id": error.client_request_id,
                "provider_request_id": error.provider_request_id,
                "upstream_status_code": error.status_code,
            },
        )
    if isinstance(error, LLMResponseError):
        return HTTPException(
            status_code=502,
            detail={
                "code": "llm_invalid_response",
                "message": "The LLM provider returned an invalid structured response.",
                "client_request_id": error.client_request_id,
                "provider_request_id": error.provider_request_id,
            },
        )
    return HTTPException(
        status_code=502,
        detail={"code": "llm_error", "message": "The LLM operation failed."},
    )


def not_found(resource: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "not_found", "message": f"{resource} was not found."},
    )
