from __future__ import annotations

import re
from typing import Any

from backend.evaluation.text_matching import (
    contains_concept,
    contains_prohibited_claim,
    normalise_text,
)
from backend.models.schemas import BenchmarkExpectation, MetricScore


class BenchmarkExpectationEvaluator:
    def evaluate(
        self,
        output: dict[str, Any],
        expected: BenchmarkExpectation | dict[str, Any] | None,
    ) -> MetricScore | None:
        if not expected:
            return None
        expectation = (
            expected
            if isinstance(expected, BenchmarkExpectation)
            else BenchmarkExpectation.model_validate(expected)
        )

        text = self._flatten_text(output)
        citations = [str(item) for item in output.get("citations_to_input", [])]

        missing_mentions = [
            term
            for term in expectation.must_mention
            if not contains_concept(text, term)
        ]
        forbidden_mentions = [
            term
            for term in expectation.must_not_mention
            if contains_prohibited_claim(text, term)
        ]
        missing_citations = [
            citation
            for citation in expectation.required_citations
            if not self._citation_satisfied(citation, citations)
        ]

        issue_count = len(missing_mentions) + len(forbidden_mentions) + len(missing_citations)
        score = max(1, 5 - issue_count)
        if issue_count == 0:
            return MetricScore(
                score=5,
                feedback=(
                    "Output satisfies concept-aware expected mentions, forbidden-claim, "
                    "and citation requirements."
                ),
            )
        return MetricScore(
            score=score,
            feedback=(
                f"Missing expected mentions/concepts: {missing_mentions or 'none'}; "
                f"unsafe forbidden claims: {forbidden_mentions or 'none'}; "
                f"missing required citations: {missing_citations or 'none'}."
            ),
        )

    def _citation_satisfied(self, required: str, citations: list[str]) -> bool:
        required_normalised = self._normalise_path(required)
        normalised_citations = [self._normalise_path(citation) for citation in citations]
        if any(
            citation == required_normalised
            or citation.startswith(f"{required_normalised}.")
            or required_normalised.startswith(f"{citation}.")
            for citation in normalised_citations
        ):
            return True
        if required_normalised == "transcript":
            return any(
                citation == "transcript"
                or citation.startswith("transcript.")
                or re.fullmatch(r"t\d+", citation)
                for citation in normalised_citations
            )
        return False

    def _flatten_text(self, value: Any) -> str:
        if isinstance(value, dict):
            return " ".join(self._flatten_text(item) for item in value.values())
        if isinstance(value, list):
            return " ".join(self._flatten_text(item) for item in value)
        return str(value)

    def _normalise_path(self, value: str) -> str:
        value = value.replace("[", ".").replace("]", "")
        return normalise_text(value).replace(" ", ".").strip(".")
