from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel

from backend.config import get_settings


class ReflectionOutput(BaseModel):
    reflection: str


class ReflectionGenerator:
    def generate(self, *, agent_type: str, weak_cases: list[dict[str, Any]]) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            return (
                "The weakest cases show gaps in specificity, citation discipline, risk framing, "
                "or advisor-ready next actions. Strengthen the prompt to demand concise evidence, "
                "clear caveats, and no real financial advice."
            )

        from openai import OpenAI

        client = OpenAI()
        settings = get_settings()
        response = client.chat.completions.create(
            model=settings.openai_judge_model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are helping improve prompts for a mock financial-advisory agent. "
                        "Reflect on failure patterns; do not write a new prompt yet."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"agent_type": agent_type, "weak_cases": weak_cases},
                        indent=2,
                        sort_keys=True,
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ReflectionOutput",
                    "schema": ReflectionOutput.model_json_schema(),
                    "strict": False,
                },
            },
        )
        content = response.choices[0].message.content or "{}"
        return ReflectionOutput.model_validate_json(content).reflection
