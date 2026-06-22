from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from backend.config import get_settings
from backend.llm import get_llm_client, is_llm_configured


class ReflectionOutput(BaseModel):
    reflection: str


class ReflectionGenerator:
    def generate(self, *, agent_type: str, weak_cases: list[dict[str, Any]]) -> str:
        if not is_llm_configured():
            return (
                "The weakest cases show gaps in specificity, citation discipline, risk framing, "
                "or advisor-ready next actions. Strengthen the prompt to demand concise evidence, "
                "clear caveats, and no real financial advice."
            )

        settings = get_settings()
        result = get_llm_client().structured_chat(
            model=settings.openai_judge_model,
            temperature=0.2,
            operation="optimisation.reflection",
            log_context={"agent_type": agent_type},
            system_prompt=(
                "You are helping improve prompts for a mock financial-advisory agent. "
                "Reflect on failure patterns; do not write a new prompt yet."
            ),
            user_message=json.dumps(
                {"agent_type": agent_type, "weak_cases": weak_cases},
                indent=2,
                sort_keys=True,
            ),
            response_model=ReflectionOutput,
        )
        return result.output.reflection
