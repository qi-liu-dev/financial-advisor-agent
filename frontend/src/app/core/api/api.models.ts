export type AgentType = 'client_summary' | 'meeting_notes' | 'investment_review';
export type PromptStatus = 'baseline' | 'candidate' | 'selected' | 'rejected';
export type OptimisationJobStatus = 'queued' | 'running' | 'completed' | 'failed';
export type BenchmarkDifficulty = 'easy' | 'medium' | 'hard';
export type MockDatasetName = 'clients' | 'portfolios' | 'meetings' | 'investment_proposals';

export const AGENT_TYPES: AgentType[] = ['client_summary', 'meeting_notes', 'investment_review'];

export const AGENT_LABELS: Record<AgentType, string> = {
  client_summary: 'Client Summary',
  meeting_notes: 'Meeting Notes',
  investment_review: 'Investment Review',
};

export interface AdvisorPreferences {
  summary_style: 'brief' | 'balanced' | 'narrative';
  detail_level: 'low' | 'medium' | 'high';
  risk_focus: 'low' | 'balanced' | 'high';
  preferred_language: string;
}

export interface ClientProfileData {
  client_id: string;
  name?: string | null;
  age?: number | null;
  household?: string | null;
  risk_tolerance: string;
  investment_horizon_years?: number | null;
  goals: string[];
  constraints: string[];
  notes?: string | null;
}

export interface PortfolioSummaryData {
  portfolio_id: string;
  client_id?: string | null;
  currency?: string | null;
  total_value?: number | null;
  asset_allocation: Record<string, number>;
  risk_notes: string[];
}

export interface TranscriptTurn {
  turn_id: string;
  speaker: string;
  text: string;
}

export interface MeetingData {
  meeting_id: string;
  client_id: string;
  date?: string | null;
  transcript: TranscriptTurn[];
}

export interface InvestmentProposalData {
  proposal_id: string;
  client_id?: string | null;
  title: string;
  proposal_summary: string;
  intended_outcome?: string | null;
  known_open_questions: string[];
}

export interface ClientSummaryPayload {
  client_profile: ClientProfileData;
  portfolio_summary: PortfolioSummaryData;
}

export interface MeetingNotesPayload {
  meeting_id: string;
  client_id: string;
  transcript: TranscriptTurn[];
}

export interface InvestmentReviewPayload {
  client_profile: ClientProfileData;
  portfolio_summary: PortfolioSummaryData;
  investment_proposal: InvestmentProposalData;
}

export type TaskPayload = ClientSummaryPayload | MeetingNotesPayload | InvestmentReviewPayload;

export interface BenchmarkExpectation {
  must_mention: string[];
  must_not_mention: string[];
  required_citations: string[];
}

export interface BenchmarkTaskResponse {
  task_id: string;
  agent_type: AgentType;
  difficulty: BenchmarkDifficulty;
  tags: string[];
  payload: TaskPayload;
  expected: BenchmarkExpectation;
}

export type MockDataItem =
  | ClientProfileData
  | PortfolioSummaryData
  | MeetingData
  | InvestmentProposalData;

export interface MockDataResponse {
  dataset: MockDatasetName;
  synthetic_only: true;
  items: MockDataItem[];
}

export interface ClientWorkspaceResponse {
  synthetic_only: true;
  client: ClientProfileData;
  portfolios: PortfolioSummaryData[];
  meetings: MeetingData[];
  investment_proposals: InvestmentProposalData[];
}

export interface BaseAgentOutput {
  summary: string;
  key_points: string[];
  risks: string[];
  next_actions: string[];
  confidence: number;
  citations_to_input: string[];
}

export interface ClientSummaryOutput extends BaseAgentOutput {
  suitability_context: string[];
  missing_information: string[];
}

export interface MeetingNotesOutput extends BaseAgentOutput {
  decisions: string[];
  follow_up_questions: string[];
}

export interface InvestmentReviewOutput extends BaseAgentOutput {
  suitability_observations: string[];
  compliance_flags: string[];
  questions_for_advisor: string[];
}

export type AgentOutput = ClientSummaryOutput | MeetingNotesOutput | InvestmentReviewOutput;

export interface TokenUsage {
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  [key: string]: number | null | undefined;
}

export interface MetricScore {
  score: number;
  feedback: string;
}

export interface EvaluationProvenance {
  rule_based_enabled: boolean;
  benchmark_checks_enabled: boolean;
  llm_judge_enabled: boolean;
  llm_provider?: string | null;
  agent_model?: string | null;
  judge_model?: string | null;
  judge_is_distinct?: boolean | null;
  caveat?: string | null;
}

export interface EvaluationResult {
  faithfulness: MetricScore;
  completeness: MetricScore;
  risk_awareness: MetricScore;
  clarity: MetricScore;
  advisor_usefulness: MetricScore;
  safety: MetricScore;
  format_correctness: MetricScore;
  benchmark_expectations?: MetricScore | null;
  latency_ms: number;
  estimated_cost: number;
  feedback: string;
  provenance?: EvaluationProvenance | null;
}

export interface RunAgentRequest {
  agent_type: AgentType;
  advisor_id?: string | null;
  task_id?: string | null;
  payload?: TaskPayload | null;
  prompt_version?: string | null;
  preferences?: AdvisorPreferences | null;
}

export interface RunAgentResponse {
  run_id: string;
  agent_type: AgentType;
  advisor_id: string;
  prompt_version: string;
  output: AgentOutput;
  latency_ms: number;
  token_usage?: TokenUsage | null;
  provider_request_id?: string | null;
  client_request_id?: string | null;
  created_at: string;
}

export interface AdvisorMemoryResponse {
  advisor_id: string;
  preferences: AdvisorPreferences;
  created_at: string;
  updated_at: string;
}

export interface OptimisationRequest {
  advisor_id?: string | null;
  max_variants: number;
  benchmark_limit?: number | null;
  repetitions?: number | null;
}

export interface OptimisationMetrics {
  quality: number;
  quality_stddev: number;
  safety: number;
  safety_stddev: number;
  latency_ms: number;
  latency_ms_stddev: number;
  estimated_cost: number;
  estimated_cost_stddev: number;
  sample_count: number;
}

export interface PromptVersionResponse {
  agent_type: AgentType;
  version: string;
  prompt: string;
  parent_version?: string | null;
  reflection?: string | null;
  average_scores?: OptimisationMetrics | null;
  status: PromptStatus;
  is_active: boolean;
  selected_at?: string | null;
  activated_at?: string | null;
  created_at: string;
}

export interface PromptActivationResponse {
  message: string;
  prompt: PromptVersionResponse;
}

export interface OptimisationSelectionPolicy {
  minimum_quality_delta: number;
  safety_tolerance: number;
  latency_tolerance_ratio: number;
  cost_tolerance_ratio: number;
}

export interface OptimisationBaselineResponse {
  version: string;
  metrics: OptimisationMetrics;
  run_ids: string[];
}

export interface OptimisationCandidateResponse {
  version: string;
  rationale: string;
  metrics: OptimisationMetrics;
  run_ids: string[];
  status: PromptStatus;
  qualifies: boolean;
  selected: boolean;
  reasons: string[];
}

export interface OptimisationResultResponse {
  optimisation_id: number;
  job_id?: string | null;
  owner_id: string;
  agent_type: AgentType;
  baseline: OptimisationBaselineResponse;
  reflection: string;
  candidates: OptimisationCandidateResponse[];
  selected_versions: string[];
  selection_policy: OptimisationSelectionPolicy;
  selection_note: string;
  created_at: string;
}

export interface OptimisationJobResponse {
  job_id: string;
  owner_id: string;
  agent_type: AgentType;
  status: OptimisationJobStatus;
  progress: number;
  request: OptimisationRequest;
  result_id?: number | null;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface RunInputSnapshot {
  task_id?: string | null;
  difficulty?: BenchmarkDifficulty | null;
  tags: string[];
  expected?: BenchmarkExpectation | null;
  payload: TaskPayload;
  advisor_id: string;
  advisor_preferences: AdvisorPreferences;
  repetition_index?: number | null;
}

export interface AgentRunSummary {
  run_id: string;
  owner_id: string;
  advisor_id: string;
  agent_type: AgentType;
  prompt_version: string;
  model_name: string;
  input_hash: string;
  latency_ms: number;
  has_evaluation: boolean;
  provider_request_id?: string | null;
  client_request_id?: string | null;
  created_at: string;
}

export interface AgentRunDetail extends AgentRunSummary {
  full_input: RunInputSnapshot;
  output: AgentOutput;
  token_usage?: TokenUsage | null;
  evaluation?: EvaluationResult | null;
  advisor_preferences?: AdvisorPreferences | null;
}

export interface PageMetadata {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface AgentRunPage {
  items: AgentRunSummary[];
  page: PageMetadata;
}

export interface PromptVersionPage {
  items: PromptVersionResponse[];
  page: PageMetadata;
}

export interface OptimisationJobPage {
  items: OptimisationJobResponse[];
  page: PageMetadata;
}

export interface OptimisationResultPage {
  items: OptimisationResultResponse[];
  page: PageMetadata;
}

export interface HealthComponent {
  status: 'ok' | 'degraded' | 'error';
  detail?: string | null;
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  service: string;
  version: string;
  database: HealthComponent;
  llm: HealthComponent;
  migration_version: number;
  active_prompt_count: number;
  encryption_enabled: boolean;
}

export interface DeleteResponse {
  deleted: boolean;
  resource_id: string;
}

export interface PurgeRunsResponse {
  deleted_count: number;
  older_than_days: number;
}

export interface AuditEventResponse {
  id: number;
  principal_id: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  request_id?: string | null;
  metadata?: Record<string, string | number | boolean | null> | null;
  created_at: string;
}

export interface AuditEventPage {
  items: AuditEventResponse[];
  page: PageMetadata;
}

export interface RunsQuery {
  page?: number;
  pageSize?: number;
  agentType?: AgentType;
  advisorId?: string;
  ownerId?: string;
  evaluated?: boolean;
}

export interface OptimisationJobsQuery {
  page?: number;
  pageSize?: number;
  status?: OptimisationJobStatus;
  ownerId?: string;
}

export interface OptimisationResultsQuery {
  page?: number;
  pageSize?: number;
  ownerId?: string;
  agentType?: AgentType;
}

export interface PromptVersionsQuery {
  page?: number;
  pageSize?: number;
}

export interface ErrorDetail {
  code?: string;
  message?: string;
  client_request_id?: string | null;
  provider_request_id?: string | null;
  upstream_status_code?: number | null;
}

export interface ApiErrorBody {
  detail?: ErrorDetail | string | Array<{ msg?: string; loc?: Array<string | number> }>;
}
