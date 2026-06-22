import { CurrencyPipe, DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize } from 'rxjs';

import { ApiService } from '../../core/api/api.service';
import {
  AGENT_LABELS,
  AgentRunDetail,
  AgentRunPage,
  AgentType,
  EvaluationResult,
  MetricScore,
} from '../../core/api/api.models';
import { ToastService } from '../../core/services/toast.service';
import { AgentOutputComponent } from '../../shared/components/agent-output/agent-output.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { IconComponent } from '../../shared/components/icon/icon.component';
import { JsonViewerComponent } from '../../shared/components/json-viewer/json-viewer.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { PaginationComponent } from '../../shared/components/pagination/pagination.component';
import { ScoreBarComponent } from '../../shared/components/score-bar/score-bar.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

type EvaluatedFilter = '' | 'true' | 'false';

interface MetricEntry {
  label: string;
  metric: MetricScore;
}

@Component({
  selector: 'app-run-evaluation-page',
  imports: [
    ReactiveFormsModule,
    DatePipe,
    DecimalPipe,
    CurrencyPipe,
    IconComponent,
    StatusBadgeComponent,
    ScoreBarComponent,
    AgentOutputComponent,
    JsonViewerComponent,
    PaginationComponent,
    EmptyStateComponent,
    LoadingStateComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './run-evaluation.page.html',
  styleUrl: './run-evaluation.page.scss',
})
export class RunEvaluationPage {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly toasts = inject(ToastService);
  private readonly destroyRef = inject(DestroyRef);

  readonly labels = AGENT_LABELS;
  readonly loadingList = signal(true);
  readonly loadingDetail = signal(false);
  readonly evaluating = signal(false);
  readonly deleting = signal(false);
  readonly runsPage = signal<AgentRunPage | null>(null);
  readonly selectedRun = signal<AgentRunDetail | null>(null);
  private pendingRunId = '';

  readonly filters = this.fb.group({
    agentType: this.fb.control<AgentType | ''>(''),
    advisorId: this.fb.control(''),
    evaluated: this.fb.control<EvaluatedFilter>(''),
  });

  constructor() {
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      this.pendingRunId = params.get('runId') ?? '';
      if (this.pendingRunId) this.selectRun(this.pendingRunId, false);
    });
    this.loadRuns(1);
  }

  loadRuns(page = 1): void {
    const filters = this.filters.getRawValue();
    this.loadingList.set(true);
    this.api
      .getRuns({
        page,
        pageSize: 20,
        agentType: filters.agentType || undefined,
        advisorId: filters.advisorId.trim() || undefined,
        evaluated: filters.evaluated === '' ? undefined : filters.evaluated === 'true',
      })
      .pipe(
        finalize(() => this.loadingList.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.runsPage.set(result);
        if (this.pendingRunId) return;
        const current = this.selectedRun();
        if (!current && result.items[0]) this.selectRun(result.items[0].run_id, false);
        if (
          current &&
          !result.items.some((run) => run.run_id === current.run_id) &&
          result.items[0]
        ) {
          this.selectRun(result.items[0].run_id, false);
        }
      });
  }

  selectRun(runId: string, updateUrl = true): void {
    if (this.selectedRun()?.run_id === runId && !this.loadingDetail()) return;
    this.loadingDetail.set(true);
    this.api
      .getRun(runId)
      .pipe(
        finalize(() => this.loadingDetail.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((run) => {
        this.selectedRun.set(run);
        this.pendingRunId = '';
        if (updateUrl)
          void this.router.navigate([], {
            relativeTo: this.route,
            queryParams: { runId },
            queryParamsHandling: 'merge',
            replaceUrl: true,
          });
      });
  }

  evaluate(): void {
    const run = this.selectedRun();
    if (!run) return;
    this.evaluating.set(true);
    this.api
      .evaluateRun(run.run_id)
      .pipe(
        finalize(() => this.evaluating.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((evaluation) => {
        this.selectedRun.set({ ...run, has_evaluation: true, evaluation });
        this.toasts.success(
          'Evaluation completed',
          'Rule, benchmark and configured LLM-judge checks were combined into the scorecard.',
        );
        const page = this.runsPage()?.page.page ?? 1;
        this.loadRuns(page);
      });
  }

  deleteSelected(): void {
    const run = this.selectedRun();
    if (
      !run ||
      !window.confirm(
        `Delete run ${run.run_id}? This removes the stored input, output and evaluation.`,
      )
    )
      return;
    this.deleting.set(true);
    this.api
      .deleteRun(run.run_id)
      .pipe(
        finalize(() => this.deleting.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => {
        this.selectedRun.set(null);
        this.toasts.success('Run deleted');
        void this.router.navigate([], {
          relativeTo: this.route,
          queryParams: { runId: null },
          queryParamsHandling: 'merge',
          replaceUrl: true,
        });
        this.loadRuns(this.runsPage()?.page.page ?? 1);
      });
  }

  metrics(evaluation: EvaluationResult): MetricEntry[] {
    const entries: MetricEntry[] = [
      { label: 'Faithfulness', metric: evaluation.faithfulness },
      { label: 'Completeness', metric: evaluation.completeness },
      { label: 'Risk awareness', metric: evaluation.risk_awareness },
      { label: 'Clarity', metric: evaluation.clarity },
      { label: 'Advisor usefulness', metric: evaluation.advisor_usefulness },
      { label: 'Safety', metric: evaluation.safety },
      { label: 'Format correctness', metric: evaluation.format_correctness },
    ];
    if (evaluation.benchmark_expectations)
      entries.push({ label: 'Benchmark expectations', metric: evaluation.benchmark_expectations });
    return entries;
  }

  shortId(id: string): string {
    return id.length > 12 ? `${id.slice(0, 10)}…` : id;
  }
}
