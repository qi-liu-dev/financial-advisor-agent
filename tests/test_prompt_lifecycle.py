from __future__ import annotations

import pytest

from backend.database import init_db
from backend.models.schemas import AgentType, PromptStatus
from backend.optimisation.prompt_store import PromptStore


def test_unselected_candidate_never_becomes_active() -> None:
    init_db()
    store = PromptStore()
    store.seed_baselines()
    store.save_prompt_version(
        agent_type=AgentType.CLIENT_SUMMARY,
        version="candidate-1",
        prompt="Candidate prompt",
        parent_version="baseline",
        reflection="test",
        average_scores=None,
        status=PromptStatus.CANDIDATE,
    )

    _, active_version = store.get_prompt(AgentType.CLIENT_SUMMARY)
    assert active_version == "baseline"

    with pytest.raises(ValueError, match="Only baseline or selected"):
        store.activate_prompt(
            agent_type=AgentType.CLIENT_SUMMARY,
            version="candidate-1",
        )

    store.mark_candidate_selection(
        agent_type=AgentType.CLIENT_SUMMARY,
        candidate_versions=["candidate-1"],
        selected_versions=[],
    )
    rejected = store.get_prompt_version(AgentType.CLIENT_SUMMARY, "candidate-1")
    assert rejected is not None
    assert rejected.status == PromptStatus.REJECTED
    assert not rejected.is_active
    assert store.get_prompt(AgentType.CLIENT_SUMMARY)[1] == "baseline"


def test_selected_prompt_requires_explicit_activation() -> None:
    init_db()
    store = PromptStore()
    store.seed_baselines()
    store.save_prompt_version(
        agent_type=AgentType.CLIENT_SUMMARY,
        version="candidate-selected",
        prompt="Selected prompt",
        parent_version="baseline",
        reflection="test",
        average_scores=None,
    )
    store.mark_candidate_selection(
        agent_type=AgentType.CLIENT_SUMMARY,
        candidate_versions=["candidate-selected"],
        selected_versions=["candidate-selected"],
    )

    selected = store.get_prompt_version(
        AgentType.CLIENT_SUMMARY,
        "candidate-selected",
    )
    assert selected is not None
    assert selected.status == PromptStatus.SELECTED
    assert not selected.is_active
    assert store.get_prompt(AgentType.CLIENT_SUMMARY)[1] == "baseline"

    activated = store.activate_prompt(
        agent_type=AgentType.CLIENT_SUMMARY,
        version="candidate-selected",
    )
    assert activated.is_active
    assert store.get_prompt(AgentType.CLIENT_SUMMARY)[1] == "candidate-selected"
