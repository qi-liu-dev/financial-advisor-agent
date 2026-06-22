import { AgentType, EvaluationResult } from './api.models';

export function agentLabel(agent: AgentType): string {
  return {
    client_summary: 'Client Summary',
    meeting_notes: 'Meeting Notes',
    investment_review: 'Investment Review',
  }[agent];
}

export function mean(values: number[]): number {
  return values.length ? values.reduce((total, value) => total + value, 0) / values.length : 0;
}

export function qualityScore(evaluation: EvaluationResult): number {
  return mean([
    evaluation.faithfulness.score,
    evaluation.completeness.score,
    evaluation.risk_awareness.score,
    evaluation.clarity.score,
    evaluation.advisor_usefulness.score,
  ]);
}

export function compactId(value: string, head = 8): string {
  return value.length <= head + 3 ? value : `${value.slice(0, head)}…`;
}
