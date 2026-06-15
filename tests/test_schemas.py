from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.models.schemas import AdvisorPreferences, ClientSummaryOutput


def test_client_summary_output_accepts_expected_shape() -> None:
    output = ClientSummaryOutput(
        summary="Mock client profile summary for advisor preparation.",
        key_points=["Moderate risk tolerance", "Liquidity need within 12 months"],
        risks=["Concentrated single-stock position"],
        next_actions=["Confirm renovation timing"],
        confidence=0.82,
        citations_to_input=["client_profile.goals", "portfolio_summary.risk_notes"],
        suitability_context=["Retirement income objective"],
        missing_information=["Tax impact of staged sale"],
    )

    assert output.confidence == 0.82
    assert output.key_points[0] == "Moderate risk tolerance"


def test_confidence_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValidationError):
        ClientSummaryOutput(
            summary="Mock client profile summary for advisor preparation.",
            key_points=["Point"],
            risks=[],
            next_actions=[],
            confidence=1.3,
            citations_to_input=[],
        )


def test_advisor_preferences_normalise_language() -> None:
    preferences = AdvisorPreferences(preferred_language=" EN ")

    assert preferences.preferred_language == "en"
