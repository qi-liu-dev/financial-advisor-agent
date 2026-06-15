from __future__ import annotations

import json
import os
import re
import time
from abc import ABC
from typing import Any, TypeVar

from pydantic import BaseModel

from backend.config import get_settings
from backend.models.schemas import AdvisorPreferences, BaseAgentOutput


OutputT = TypeVar("OutputT", bound=BaseAgentOutput)


class AgentRunResult(BaseModel):
    output: BaseAgentOutput
    latency_ms: float
    token_usage: dict[str, Any] | None
    model_name: str
    prompt_version: str


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
        start = time.perf_counter()
        output, usage = self._call_openai(
            model=settings.openai_model,
            system_prompt=prompt,
            payload=payload,
            preferences=preferences,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        return AgentRunResult(
            output=output,
            latency_ms=latency_ms,
            token_usage=usage,
            model_name=settings.openai_model,
            prompt_version=prompt_version,
        )

    def _call_openai(
        self,
        model: str,
        system_prompt: str,
        payload: dict[str, Any],
        preferences: AdvisorPreferences,
    ) -> tuple[OutputT, dict[str, Any] | None]:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required to run agents with the OpenAI API.")

        from openai import OpenAI

        client = OpenAI()
        schema = self.output_schema.model_json_schema()
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": self._build_user_message(payload=payload, preferences=preferences),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": self.output_schema.__name__,
                    "schema": schema,
                    "strict": False,
                },
            },
        )
        content = response.choices[0].message.content or "{}"
        output = self._parse_structured_output(content)
        usage = response.usage.model_dump() if response.usage else None
        return output, usage

    def _build_user_message(self, payload: dict[str, Any], preferences: AdvisorPreferences) -> str:
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

    def _parse_structured_output(self, content: str) -> OutputT:
        try:
            return self.output_schema.model_validate_json(content)
        except ValueError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                raise
            return self.output_schema.model_validate_json(match.group(0))
