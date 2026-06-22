import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { distinctUntilChanged, finalize, forkJoin, startWith } from 'rxjs';

import { ApiService } from '../../core/api/api.service';
import {
  AGENT_LABELS,
  AgentType,
  AdvisorPreferences,
  BenchmarkTaskResponse,
  ClientWorkspaceResponse,
  PromptVersionResponse,
  RunAgentRequest,
  RunAgentResponse,
  TaskPayload,
} from '../../core/api/api.models';
import { SessionService } from '../../core/auth/session.service';
import { ToastService } from '../../core/services/toast.service';
import { AgentOutputComponent } from '../../shared/components/agent-output/agent-output.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { IconComponent } from '../../shared/components/icon/icon.component';
import { JsonViewerComponent } from '../../shared/components/json-viewer/json-viewer.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

type InputSource = 'benchmark' | 'custom';

@Component({
  selector: 'app-agent-runner-page',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    DatePipe,
    DecimalPipe,
    IconComponent,
    StatusBadgeComponent,
    AgentOutputComponent,
    JsonViewerComponent,
    EmptyStateComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './agent-runner.page.html',
  styleUrl: './agent-runner.page.scss',
})
export class AgentRunnerPage {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly session = inject(SessionService);
  private readonly toasts = inject(ToastService);
  private readonly destroyRef = inject(DestroyRef);

  readonly labels = AGENT_LABELS;
  readonly loadingResources = signal(true);
  readonly running = signal(false);
  readonly tasks = signal<BenchmarkTaskResponse[]>([]);
  readonly promptVersions = signal<PromptVersionResponse[]>([]);
  readonly result = signal<RunAgentResponse | null>(null);
  readonly importedWorkspace = signal<ClientWorkspaceResponse | null>(null);
  readonly payloadError = signal('');
  private pendingTaskId = '';
  private pendingClientId = '';

  readonly form = this.fb.group({
    agentType: this.fb.control<AgentType>('client_summary'),
    source: this.fb.control<InputSource>('benchmark'),
    taskId: this.fb.control(''),
    promptVersion: this.fb.control(''),
    advisorId: this.fb.control(this.session.advisorId(), { validators: [Validators.required] }),
    summaryStyle: this.fb.control<AdvisorPreferences['summary_style']>('balanced'),
    detailLevel: this.fb.control<AdvisorPreferences['detail_level']>('medium'),
    riskFocus: this.fb.control<AdvisorPreferences['risk_focus']>('balanced'),
    preferredLanguage: this.fb.control('en'),
    customPayload: this.fb.control(this.defaultPayload('client_summary')),
  });

  matchingTasks(): BenchmarkTaskResponse[] {
    return this.tasks().filter((task) => task.agent_type === this.form.controls.agentType.value);
  }

  selectedTask(): BenchmarkTaskResponse | null {
    return this.tasks().find((task) => task.task_id === this.form.controls.taskId.value) ?? null;
  }

  selectedPrompt(): PromptVersionResponse | null {
    return (
      this.promptVersions().find(
        (prompt) => prompt.version === this.form.controls.promptVersion.value,
      ) ?? null
    );
  }

  constructor() {
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const agent = params.get('agent');
      if (this.isAgentType(agent)) this.form.controls.agentType.setValue(agent);
      this.pendingTaskId = params.get('task') ?? '';
      this.pendingClientId = params.get('clientId') ?? '';
      if (this.pendingClientId) {
        this.form.controls.source.setValue('custom');
        this.importWorkspace(this.pendingClientId);
      }
      this.applyPendingTask();
    });

    this.form.controls.agentType.valueChanges
      .pipe(
        startWith(this.form.controls.agentType.value),
        distinctUntilChanged(),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((agent) => {
        this.result.set(null);
        this.loadPrompts(agent);
        this.ensureMatchingTask(agent);
        if (this.form.controls.source.value === 'custom') {
          const workspace = this.importedWorkspace();
          this.form.controls.customPayload.setValue(
            workspace ? this.payloadFromWorkspace(workspace, agent) : this.defaultPayload(agent),
          );
        }
      });

    this.api
      .getTasks()
      .pipe(
        finalize(() => this.loadingResources.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((tasks) => {
        this.tasks.set(tasks);
        this.applyPendingTask();
        this.ensureMatchingTask(this.form.controls.agentType.value);
      });
  }

  setSource(source: InputSource): void {
    this.form.controls.source.setValue(source);
    this.payloadError.set('');
    if (source === 'custom' && !this.form.controls.customPayload.value.trim()) {
      this.form.controls.customPayload.setValue(
        this.defaultPayload(this.form.controls.agentType.value),
      );
    }
  }

  run(): void {
    this.payloadError.set('');
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    const value = this.form.getRawValue();
    const body: RunAgentRequest = {
      agent_type: value.agentType,
      advisor_id: value.advisorId.trim(),
      prompt_version: value.promptVersion || undefined,
      preferences: {
        summary_style: value.summaryStyle,
        detail_level: value.detailLevel,
        risk_focus: value.riskFocus,
        preferred_language: value.preferredLanguage.trim() || 'en',
      },
    };

    if (value.source === 'benchmark') {
      if (!value.taskId) {
        this.toasts.warning('Select a benchmark task');
        return;
      }
      body.task_id = value.taskId;
    } else {
      try {
        const parsed = JSON.parse(value.customPayload) as unknown;
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
          throw new Error('Payload must be a JSON object.');
        body.payload = parsed as TaskPayload;
      } catch (error) {
        this.payloadError.set(error instanceof Error ? error.message : 'Invalid JSON payload.');
        return;
      }
    }

    this.session.setAdvisorId(value.advisorId);
    this.running.set(true);
    this.result.set(null);
    this.api
      .runAgent(body)
      .pipe(
        finalize(() => this.running.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.result.set(result);
        this.toasts.success(
          'Agent run completed',
          `Run ${result.run_id.slice(0, 8)} used prompt ${result.prompt_version}.`,
        );
        window.setTimeout(
          () =>
            document
              .querySelector('#run-result')
              ?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
          50,
        );
      });
  }

  resetCustomPayload(): void {
    const workspace = this.importedWorkspace();
    this.form.controls.customPayload.setValue(
      workspace
        ? this.payloadFromWorkspace(workspace, this.form.controls.agentType.value)
        : this.defaultPayload(this.form.controls.agentType.value),
    );
    this.payloadError.set('');
  }

  private loadPrompts(agent: AgentType): void {
    this.api
      .getPromptVersions(agent, { pageSize: 200 })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((page) => this.promptVersions.set(page.items));
  }

  private ensureMatchingTask(agent: AgentType): void {
    const current = this.tasks().find((task) => task.task_id === this.form.controls.taskId.value);
    if (!current || current.agent_type !== agent) {
      this.form.controls.taskId.setValue(
        this.tasks().find((task) => task.agent_type === agent)?.task_id ?? '',
      );
    }
  }

  private applyPendingTask(): void {
    if (!this.pendingTaskId || !this.tasks().length) return;
    const task = this.tasks().find((item) => item.task_id === this.pendingTaskId);
    if (!task) return;
    this.form.controls.agentType.setValue(task.agent_type);
    this.form.controls.taskId.setValue(task.task_id);
    this.form.controls.source.setValue('benchmark');
    this.pendingTaskId = '';
  }

  private importWorkspace(clientId: string): void {
    forkJoin({ workspace: this.api.getClientWorkspace(clientId), tasks: this.api.getTasks() })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(({ workspace, tasks }) => {
        this.tasks.set(tasks);
        this.importedWorkspace.set(workspace);
        this.form.controls.customPayload.setValue(
          this.payloadFromWorkspace(workspace, this.form.controls.agentType.value),
        );
        this.toasts.info(
          'Synthetic workspace imported',
          `${workspace.client.name ?? workspace.client.client_id} is ready as a custom payload.`,
        );
      });
  }

  private payloadFromWorkspace(workspace: ClientWorkspaceResponse, agent: AgentType): string {
    let payload: TaskPayload;
    if (agent === 'meeting_notes') {
      const meeting = workspace.meetings[0];
      payload = meeting
        ? {
            meeting_id: meeting.meeting_id,
            client_id: meeting.client_id,
            transcript: meeting.transcript,
          }
        : JSON.parse(this.defaultPayload(agent));
    } else if (agent === 'investment_review') {
      payload =
        workspace.portfolios[0] && workspace.investment_proposals[0]
          ? {
              client_profile: workspace.client,
              portfolio_summary: workspace.portfolios[0],
              investment_proposal: workspace.investment_proposals[0],
            }
          : JSON.parse(this.defaultPayload(agent));
    } else {
      payload = workspace.portfolios[0]
        ? { client_profile: workspace.client, portfolio_summary: workspace.portfolios[0] }
        : JSON.parse(this.defaultPayload(agent));
    }
    return JSON.stringify(payload, null, 2);
  }

  private defaultPayload(agent: AgentType): string {
    const client = {
      client_id: 'client-demo',
      name: 'Synthetic Client',
      age: 58,
      household: 'Couple',
      risk_tolerance: 'balanced',
      investment_horizon_years: 8,
      goals: ['Retire sustainably', 'Preserve purchasing power'],
      constraints: ['Moderate liquidity need'],
      notes: 'Synthetic demonstration data only.',
    };
    const portfolio = {
      portfolio_id: 'portfolio-demo',
      client_id: 'client-demo',
      currency: 'EUR',
      total_value: 850000,
      asset_allocation: { equities: 62, bonds: 28, cash: 10 },
      risk_notes: ['Equity exposure may be high relative to the retirement horizon'],
    };
    if (agent === 'meeting_notes') {
      return JSON.stringify(
        {
          meeting_id: 'meeting-demo',
          client_id: 'client-demo',
          transcript: [
            {
              turn_id: '1',
              speaker: 'Advisor',
              text: 'How comfortable are you with the current portfolio volatility?',
            },
            {
              turn_id: '2',
              speaker: 'Client',
              text: 'I am concerned about a large drawdown before retirement.',
            },
            {
              turn_id: '3',
              speaker: 'Advisor',
              text: 'We will review the strategic asset allocation and retirement cash-flow scenarios.',
            },
          ],
        },
        null,
        2,
      );
    }
    if (agent === 'investment_review') {
      return JSON.stringify(
        {
          client_profile: client,
          portfolio_summary: portfolio,
          investment_proposal: {
            proposal_id: 'proposal-demo',
            client_id: 'client-demo',
            title: 'Reduce equity concentration',
            proposal_summary:
              'Shift 10% from global equities to high-quality bonds over two tranches.',
            intended_outcome: 'Reduce downside risk while preserving long-term return potential',
            known_open_questions: [
              'Confirm tax implications',
              'Confirm acceptable implementation timing',
            ],
          },
        },
        null,
        2,
      );
    }
    return JSON.stringify({ client_profile: client, portfolio_summary: portfolio }, null, 2);
  }

  private isAgentType(value: string | null): value is AgentType {
    return value === 'client_summary' || value === 'meeting_notes' || value === 'investment_review';
  }
}
