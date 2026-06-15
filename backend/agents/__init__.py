from backend.agents.base import AgentRunResult, FinancialAdvisorAgent
from backend.agents.client_summary_agent import ClientSummaryAgent
from backend.agents.investment_review_agent import InvestmentProposalReviewAgent
from backend.agents.meeting_notes_agent import MeetingNotesAgent
from backend.models.schemas import AgentType


AGENT_CLASSES = {
    AgentType.CLIENT_SUMMARY: ClientSummaryAgent,
    AgentType.MEETING_NOTES: MeetingNotesAgent,
    AgentType.INVESTMENT_REVIEW: InvestmentProposalReviewAgent,
}


BASELINE_PROMPTS = {
    agent_type: agent_cls.BASELINE_PROMPT for agent_type, agent_cls in AGENT_CLASSES.items()
}


def get_agent(agent_type: AgentType) -> FinancialAdvisorAgent:
    return AGENT_CLASSES[agent_type]()
