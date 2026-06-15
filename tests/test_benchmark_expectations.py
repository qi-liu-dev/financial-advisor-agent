from __future__ import annotations

from backend.evaluation.benchmark_expectations import BenchmarkExpectationEvaluator


def test_benchmark_expectations_pass_when_mentions_and_citations_match() -> None:
    output = {
        "summary": "The client has a single-stock concentration and a liquidity need.",
        "key_points": ["Retirement income should be reviewed by the advisor."],
        "risks": ["Single-stock concentration"],
        "next_actions": ["Confirm liquidity timing"],
        "confidence": 0.9,
        "citations_to_input": ["client_profile.constraints", "portfolio_summary.risk_notes"],
    }
    expected = {
        "must_mention": ["single-stock", "liquidity"],
        "must_not_mention": ["guaranteed return"],
        "required_citations": ["client_profile.constraints", "portfolio_summary.risk_notes"],
    }

    score = BenchmarkExpectationEvaluator().evaluate(output, expected)

    assert score is not None
    assert score.score == 5


def test_benchmark_expectations_penalise_missing_and_forbidden_content() -> None:
    output = {
        "summary": "This has a guaranteed return.",
        "key_points": ["Income focus"],
        "risks": [],
        "next_actions": [],
        "confidence": 0.7,
        "citations_to_input": [],
    }
    expected = {
        "must_mention": ["liquidity"],
        "must_not_mention": ["guaranteed return"],
        "required_citations": ["portfolio_summary.risk_notes"],
    }

    score = BenchmarkExpectationEvaluator().evaluate(output, expected)

    assert score is not None
    assert score.score == 2
    assert "Missing expected mentions" in score.feedback
