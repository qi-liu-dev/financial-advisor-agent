import { CurrencyPipe, DatePipe, DecimalPipe, PercentPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { catchError, finalize, forkJoin, from, map, mergeMap, of, switchMap, toArray } from 'rxjs';

import { ApiService } from '../../core/api/api.service';
import {
  AGENT_LABELS,
  AGENT_TYPES,
  AgentRunDetail,
  AgentRunPage,
  AgentRunSummary,
  AgentType,
  HealthResponse,
  OptimisationJobResponse,
  PromptVersionResponse,
} from '../../core/api/api.models';
import { mean, qualityScore } from '../../core/api/api.helpers';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { IconComponent } from '../../shared/components/icon/icon.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { MetricCardComponent } from '../../shared/components/metric-card/metric-card.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

interface AgentOverview {
  agent: AgentType;
  runs: number;
  evaluated: number;
  averageLatency: number;
  quality: number;
  safety: number;
  activePrompt?: PromptVersionResponse | null;
}

@Component({
  selector: 'app-dashboard-page',
  imports: [
    RouterLink,
    DatePipe,
    DecimalPipe,
    CurrencyPipe,
    PercentPipe,
    MetricCardComponent,
    StatusBadgeComponent,
    EmptyStateComponent,
    LoadingStateComponent,
    IconComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './dashboard.page.html',
  styleUrl: './dashboard.page.scss',
})
export class DashboardPage {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);

  readonly loading = signal(true);
  readonly health = signal<HealthResponse | null>(null);
  readonly runsPage = signal<AgentRunPage | null>(null);
  readonly evaluatedTotal = signal(0);
  readonly runDetails = signal<AgentRunDetail[]>([]);
  readonly activePrompts = signal<Partial<Record<AgentType, PromptVersionResponse | null>>>({});
  readonly jobs = signal<OptimisationJobResponse[]>([]);

  readonly totalRuns = computed(() => this.runsPage()?.page.total_items ?? 0);
  readonly averageLatency = computed(() =>
    mean(this.runsPage()?.items.map((run) => run.latency_ms) ?? []),
  );
  readonly averageQuality = computed(() =>
    mean(
      this.runDetails().flatMap((run) => (run.evaluation ? [qualityScore(run.evaluation)] : [])),
    ),
  );
  readonly averageSafety = computed(() =>
    mean(this.runDetails().flatMap((run) => (run.evaluation ? [run.evaluation.safety.score] : []))),
  );
  readonly trackedCost = computed(() =>
    this.runDetails().reduce((total, run) => total + (run.evaluation?.estimated_cost ?? 0), 0),
  );
  readonly evaluationCoverage = computed(() =>
    this.totalRuns() ? this.evaluatedTotal() / this.totalRuns() : 0,
  );
  readonly recentRuns = computed(() => this.runsPage()?.items.slice(0, 8) ?? []);
  readonly activeJobs = computed(() =>
    this.jobs().filter((job) => job.status === 'queued' || job.status === 'running'),
  );
  readonly agentRows = computed<AgentOverview[]>(() => {
    const summaries = this.runsPage()?.items ?? [];
    const details = this.runDetails();
    return AGENT_TYPES.map((agent) => {
      const agentRuns = summaries.filter((run) => run.agent_type === agent);
      const evaluations = details
        .filter((run) => run.agent_type === agent && run.evaluation)
        .map((run) => run.evaluation!);
      return {
        agent,
        runs: agentRuns.length,
        evaluated: evaluations.length,
        averageLatency: mean(agentRuns.map((run) => run.latency_ms)),
        quality: mean(evaluations.map(qualityScore)),
        safety: mean(evaluations.map((evaluation) => evaluation.safety.score)),
        activePrompt: this.activePrompts()[agent],
      };
    });
  });

  readonly labels = AGENT_LABELS;
  readonly agentTypes = AGENT_TYPES;

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    const prompts = forkJoin({
      client_summary: this.api.getActivePrompt('client_summary').pipe(catchError(() => of(null))),
      meeting_notes: this.api.getActivePrompt('meeting_notes').pipe(catchError(() => of(null))),
      investment_review: this.api
        .getActivePrompt('investment_review')
        .pipe(catchError(() => of(null))),
    });

    forkJoin({
      health: this.api.getHealth().pipe(catchError(() => of(null))),
      runs: this.api.getRuns({ page: 1, pageSize: 200 }),
      evaluated: this.api.getRuns({ page: 1, pageSize: 1, evaluated: true }),
      prompts,
      jobs: this.api
        .getOptimisations({ page: 1, pageSize: 12 })
        .pipe(
          catchError(() =>
            of({ items: [], page: { page: 1, page_size: 12, total_items: 0, total_pages: 0 } }),
          ),
        ),
    })
      .pipe(
        switchMap((summary) => {
          const evaluatedRuns = summary.runs.items.filter((run) => run.has_evaluation).slice(0, 50);
          if (!evaluatedRuns.length) return of({ ...summary, details: [] as AgentRunDetail[] });
          return from(evaluatedRuns).pipe(
            mergeMap((run) => this.api.getRun(run.run_id).pipe(catchError(() => of(null))), 6),
            toArray(),
            map((details) => ({
              ...summary,
              details: details.filter((item): item is AgentRunDetail => item !== null),
            })),
          );
        }),
        finalize(() => this.loading.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((data) => {
        this.health.set(data.health);
        this.runsPage.set(data.runs);
        this.evaluatedTotal.set(data.evaluated.page.total_items);
        this.activePrompts.set(data.prompts);
        this.jobs.set(data.jobs.items);
        this.runDetails.set(data.details);
      });
  }

  compactId(run: AgentRunSummary): string {
    return run.run_id.length > 10 ? `${run.run_id.slice(0, 8)}…` : run.run_id;
  }

  sampleLabel(): string {
    const loaded = this.runsPage()?.items.length ?? 0;
    const total = this.totalRuns();
    return total > loaded ? `Latest ${loaded} runs` : 'All recorded runs';
  }
}
