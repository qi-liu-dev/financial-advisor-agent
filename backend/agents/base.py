from __future__ import annotations

import json
from abc import ABC
from typing import Any, TypeVar

from pydantic import BaseModel

from backend.config import get_settings
from backend.llm import StructuredChatResult, get_llm_client
from backend.models.schemas import AdvisorPreferences, BaseAgentOutput


OutputT = TypeVar("OutputT", bound=BaseAgentOutput)


class AgentRunResult(BaseModel):
    output: BaseAgentOutput
    latency_ms: float
    token_usage: dict[str, Any] | None
    model_name: str
    prompt_version: str
    provider_request_id: str | None = None
    client_request_id: str | None = None


class FinancialAdvisorAgent(ABC):
    agent_type: str
    output_schema: type[OutputT]
    BASELINE_PROMPT: str

    def run(
        self,
        payload: dict[str, Any],
        preferences: AdvisorPreferences,
        prompt: str,
        prompt_version: str,
    ) -> AgentRunResult:
        settings = get_settings()
        llm_result = self._call_llm(
            model=settings.openai_model,
            system_prompt=prompt,
            payload=payload,
            preferences=preferences,
            prompt_version=prompt_version,
        )
        return AgentRunResult(
            output=llm_result.output,
            latency_ms=llm_result.latency_ms,
            token_usage=llm_result.token_usage,
            model_name=llm_result.model,
            prompt_version=prompt_version,
            provider_request_id=llm_result.provider_request_id,
            client_request_id=llm_result.client_request_id,
        )

    def _call_llm(
        self,
        *,
        model: str,
        system_prompt: str,
        payload: dict[str, Any],
        preferences: AdvisorPreferences,
        prompt_version: str,
    ) -> StructuredChatResult[OutputT]:
        return get_llm_client().structured_chat(
            model=model,
            system_prompt=system_prompt,
            user_message=self._build_user_message(
                payload=payload,
                preferences=preferences,
            ),
            response_model=self.output_schema,
            temperature=0.2,
            operation=f"agent.{self.agent_type}",
            log_context={
                "agent_type": self.agent_type,
                "prompt_version": prompt_version,
            },
        )

    def _build_user_message(
        self,
        payload: dict[str, Any],
        preferences: AdvisorPreferences,
    ) -> str:
        return json.dumps(
            {
                "task_payload": payload,
                "advisor_preferences": preferences.model_dump(),
                "important_boundary": (
                    "Use only the mock input. Do not recommend transactions, products, or allocation changes. "
                    "Frame observations as advisor-support notes, not financial advice."
                ),
            },
            indent=2,
            sort_keys=True,
        )
