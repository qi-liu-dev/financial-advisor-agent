import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AdvisorMemoryResponse,
  AdvisorPreferences,
  AgentRunDetail,
  AgentRunPage,
  AgentType,
  AuditEventPage,
  BenchmarkTaskResponse,
  ClientWorkspaceResponse,
  DeleteResponse,
  EvaluationResult,
  HealthResponse,
  MockDataResponse,
  MockDatasetName,
  OptimisationJobPage,
  OptimisationJobResponse,
  OptimisationJobsQuery,
  OptimisationRequest,
  OptimisationResultPage,
  OptimisationResultResponse,
  OptimisationResultsQuery,
  PromptActivationResponse,
  PromptVersionPage,
  PromptVersionResponse,
  PromptVersionsQuery,
  PurgeRunsResponse,
  RunAgentRequest,
  RunAgentResponse,
  RunsQuery,
} from './api.models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  getHealth(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.baseUrl}/health`);
  }

  getTasks(agentType?: AgentType): Observable<BenchmarkTaskResponse[]> {
    let params = new HttpParams();
    if (agentType) params = params.set('agent_type', agentType);
    return this.http.get<BenchmarkTaskResponse[]>(`${this.baseUrl}/tasks`, { params });
  }

  getMockData(dataset: MockDatasetName): Observable<MockDataResponse> {
    return this.http.get<MockDataResponse>(`${this.baseUrl}/mock-data/${dataset}`);
  }

  getClientWorkspace(clientId: string): Observable<ClientWorkspaceResponse> {
    return this.http.get<ClientWorkspaceResponse>(
      `${this.baseUrl}/mock-data/workspaces/${encodeURIComponent(clientId)}`,
    );
  }

  runAgent(body: RunAgentRequest): Observable<RunAgentResponse> {
    return this.http.post<RunAgentResponse>(`${this.baseUrl}/run-agent`, body);
  }

  evaluateRun(runId: string): Observable<EvaluationResult> {
    return this.http.post<EvaluationResult>(
      `${this.baseUrl}/evaluate-run/${encodeURIComponent(runId)}`,
      {},
    );
  }

  getRuns(query: RunsQuery = {}): Observable<AgentRunPage> {
    let params = new HttpParams()
      .set('page', query.page ?? 1)
      .set('page_size', query.pageSize ?? 25);
    if (query.agentType) params = params.set('agent_type', query.agentType);
    if (query.advisorId) params = params.set('advisor_id', query.advisorId);
    if (query.ownerId) params = params.set('owner_id', query.ownerId);
    if (query.evaluated !== undefined) params = params.set('evaluated', query.evaluated);
    return this.http.get<AgentRunPage>(`${this.baseUrl}/runs`, { params });
  }

  getRun(runId: string): Observable<AgentRunDetail> {
    return this.http.get<AgentRunDetail>(`${this.baseUrl}/runs/${encodeURIComponent(runId)}`);
  }

  deleteRun(runId: string): Observable<DeleteResponse> {
    return this.http.delete<DeleteResponse>(`${this.baseUrl}/runs/${encodeURIComponent(runId)}`);
  }

  purgeRuns(olderThanDays: number, allOwners = false): Observable<PurgeRunsResponse> {
    const params = new HttpParams()
      .set('older_than_days', olderThanDays)
      .set('all_owners', allOwners);
    return this.http.delete<PurgeRunsResponse>(`${this.baseUrl}/runs`, { params });
  }

  getPromptVersions(
    agentType: AgentType,
    query: PromptVersionsQuery = {},
  ): Observable<PromptVersionPage> {
    const params = new HttpParams()
      .set('page', query.page ?? 1)
      .set('page_size', query.pageSize ?? 50);
    return this.http.get<PromptVersionPage>(`${this.baseUrl}/prompt-versions/${agentType}`, {
      params,
    });
  }

  getActivePrompt(agentType: AgentType): Observable<PromptVersionResponse> {
    return this.http.get<PromptVersionResponse>(`${this.baseUrl}/prompts/${agentType}/active`);
  }

  activatePrompt(agentType: AgentType, version: string): Observable<PromptActivationResponse> {
    return this.http.post<PromptActivationResponse>(
      `${this.baseUrl}/prompts/${agentType}/${encodeURIComponent(version)}/activate`,
      {},
    );
  }

  createOptimisation(
    agentType: AgentType,
    body: OptimisationRequest,
  ): Observable<OptimisationJobResponse> {
    return this.http.post<OptimisationJobResponse>(
      `${this.baseUrl}/optimisations/${agentType}`,
      body,
    );
  }

  getOptimisation(jobId: string): Observable<OptimisationJobResponse> {
    return this.http.get<OptimisationJobResponse>(
      `${this.baseUrl}/optimisations/${encodeURIComponent(jobId)}`,
    );
  }

  getOptimisations(query: OptimisationJobsQuery = {}): Observable<OptimisationJobPage> {
    let params = new HttpParams()
      .set('page', query.page ?? 1)
      .set('page_size', query.pageSize ?? 25);
    if (query.status) params = params.set('status', query.status);
    if (query.ownerId) params = params.set('owner_id', query.ownerId);
    return this.http.get<OptimisationJobPage>(`${this.baseUrl}/optimisations`, { params });
  }

  getOptimisationResults(query: OptimisationResultsQuery = {}): Observable<OptimisationResultPage> {
    let params = new HttpParams()
      .set('page', query.page ?? 1)
      .set('page_size', query.pageSize ?? 25);
    if (query.ownerId) params = params.set('owner_id', query.ownerId);
    if (query.agentType) params = params.set('agent_type', query.agentType);
    return this.http.get<OptimisationResultPage>(`${this.baseUrl}/optimisation-results`, {
      params,
    });
  }

  getOptimisationResult(optimisationId: number): Observable<OptimisationResultResponse> {
    return this.http.get<OptimisationResultResponse>(
      `${this.baseUrl}/optimisation-results/${optimisationId}`,
    );
  }

  getMemory(advisorId: string): Observable<AdvisorMemoryResponse> {
    return this.http.get<AdvisorMemoryResponse>(
      `${this.baseUrl}/memory/${encodeURIComponent(advisorId)}`,
    );
  }

  updateMemory(
    advisorId: string,
    preferences: AdvisorPreferences,
  ): Observable<AdvisorMemoryResponse> {
    return this.http.post<AdvisorMemoryResponse>(
      `${this.baseUrl}/memory/${encodeURIComponent(advisorId)}`,
      { preferences },
    );
  }

  deleteMemory(advisorId: string): Observable<DeleteResponse> {
    return this.http.delete<DeleteResponse>(
      `${this.baseUrl}/memory/${encodeURIComponent(advisorId)}`,
    );
  }

  getAuditEvents(page = 1, pageSize = 50, principalId?: string): Observable<AuditEventPage> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (principalId) params = params.set('principal_id', principalId);
    return this.http.get<AuditEventPage>(`${this.baseUrl}/audit-events`, { params });
  }
}
