from __future__ import annotations

import json

from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.llm import get_llm_client, is_llm_configured


class PromptVariant(BaseModel):
    rationale: str
    prompt: str


class PromptVariants(BaseModel):
    variants: list[PromptVariant] = Field(..., min_length=1)


class PromptMutator:
    def generate(
        self,
        *,
        baseline_prompt: str,
        reflection: str,
        max_variants: int,
    ) -> list[PromptVariant]:
        if not is_llm_configured():
            return self._offline_variants(baseline_prompt, reflection, max_variants)

        settings = get_settings()
        result = get_llm_client().structured_chat(
            model=settings.openai_judge_model,
            temperature=0.5,
            operation="optimisation.prompt_mutation",
            system_prompt=(
                "Generate prompt variants for a mock advisor-support agent. "
                "Each variant must improve evaluation quality without increasing unsafe advice. "
                "Keep disclaimers and structured JSON requirements."
            ),
            user_message=json.dumps(
                {
                    "baseline_prompt": baseline_prompt,
                    "reflection": reflection,
                    "max_variants": max_variants,
                    "constraints": [
                        "Do not claim to implement full GEPA.",
                        "Do not enable real financial advice.",
                        "Preserve JSON-only structured output requirement.",
                    ],
                },
                indent=2,
                sort_keys=True,
            ),
            response_model=PromptVariants,
        )
        return result.output.variants[:max_variants]

    def _offline_variants(
        self,
        baseline_prompt: str,
        reflection: str,
        max_variants: int,
    ) -> list[PromptVariant]:
        templates = [
            (
                "Adds explicit evidence discipline and missing-information checks.",
                "\n\nAdditional optimisation instruction: For each key point, prefer directly supported facts, "
                "flag unsupported assumptions, and cite the exact input area. If information is missing, add it "
                "to missing-information or follow-up fields instead of guessing.",
            ),
            (
                "Strengthens safety and advisor-review framing.",
                "\n\nAdditional optimisation instruction: Use advisor-support wording throughout. Avoid imperative "
                "client recommendations, product endorsements, approvals, or guarantees. Convert advice-like language "
                "into review prompts for a qualified human advisor.",
            ),
            (
                "Improves actionability and concise formatting.",
                "\n\nAdditional optimisation instruction: Make next_actions specific, assignable, and human-reviewable. "
                "Keep summaries concise and align detail level to advisor preferences.",
            ),
        ]
        variants = [
            PromptVariant(
                rationale=f"{rationale} Reflection used: {reflection[:240]}",
                prompt=baseline_prompt + addition,
            )
            for rationale, addition in templates
        ]
        return variants[:max_variants]
