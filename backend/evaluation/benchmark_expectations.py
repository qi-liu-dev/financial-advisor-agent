from __future__ import annotations

import re
from typing import Any

from backend.models.schemas import MetricScore


class BenchmarkExpectationEvaluator:
    def evaluate(
        self,
        output: dict[str, Any],
        expected: dict[str, Any] | None,
    ) -> MetricScore | None:
        if not expected:
            return None

        text = self._normalise(self._flatten_text(output))
        citations = [str(item) for item in output.get("citations_to_input", [])]

        missing_mentions = [
            term
            for term in expected.get("must_mention", [])
            if self._normalise(term) not in text
        ]
        forbidden_mentions = [
            term
            for term in expected.get("must_not_mention", [])
            if self._normalise(term) in text
        ]
        missing_citations = [
            citation
            for citation in expected.get("required_citations", [])
            if not self._citation_satisfied(citation, citations)
        ]

        issue_count = len(missing_mentions) + len(forbidden_mentions) + len(missing_citations)
        score = max(1, 5 - issue_count)
        if issue_count == 0:
            return MetricScore(
                score=5,
                feedback="Output satisfies benchmark-specific expected mentions, forbidden phrases, and citation requirements.",
            )
        return MetricScore(
            score=score,
            feedback=(
                f"Missing expected mentions: {missing_mentions or 'none'}; "
                f"forbidden mentions: {forbidden_mentions or 'none'}; "
                f"missing required citations: {missing_citations or 'none'}."
            ),
        )

    def _citation_satisfied(self, required: str, citations: list[str]) -> bool:
        required_normalised = self._normalise(required)
        citation_text = " ".join(self._normalise(citation) for citation in citations)
        if required_normalised in citation_text:
            return True
        if required_normalised == "transcript":
            return any(re.fullmatch(r"t\d+", citation.strip().lower()) for citation in citations)
        return False

    def _flatten_text(self, value: Any) -> str:
        if isinstance(value, dict):
            return " ".join(self._flatten_text(item) for item in value.values())
        if isinstance(value, list):
            return " ".join(self._flatten_text(item) for item in value)
        return str(value)

    def _normalise(self, value: str) -> str:
        value = value.lower().replace("-", " ")
        return re.sub(r"\s+", " ", value).strip()
