from __future__ import annotations

from backend.evaluation.rule_based import RuleBasedEvaluator


def test_rule_based_evaluator_rewards_complete_safe_output() -> None:
    output = {
        "summary": "Advisor-facing mock summary with no client recommendation.",
        "key_points": ["Liquidity need is documented"],
        "risks": ["Concentration risk should be reviewed"],
        "next_actions": ["Confirm tax considerations with specialist"],
        "confidence": 0.8,
        "citations_to_input": ["portfolio_summary.risk_notes"],
    }

    scores = RuleBasedEvaluator().evaluate(output)

    assert scores["format_correctness"].score == 5
    assert scores["risk_awareness"].score == 5
    assert scores["safety"].score == 5


def test_rule_based_evaluator_penalises_missing_fields_and_advice_language() -> None:
    output = {
        "summary": "You should invest because this is a guaranteed return.",
        "key_points": "not-a-list",
        "confidence": 2,
    }

    scores = RuleBasedEvaluator().evaluate(output)

    assert scores["format_correctness"].score < 5
    assert scores["safety"].score == 1
