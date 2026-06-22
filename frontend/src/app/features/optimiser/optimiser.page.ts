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
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import {
  Subscription,
  catchError,
  finalize,
  forkJoin,
  of,
  switchMap,
  takeWhile,
  tap,
  timer,
} from 'rxjs';

import { environment } from '../../../environments/environment';
import { ApiService } from '../../core/api/api.service';
import {
  AGENT_LABELS,
  AgentType,
  OptimisationCandidateResponse,
  OptimisationJobResponse,
  OptimisationResultResponse,
  PromptVersionResponse,
} from '../../core/api/api.models';
import { SessionService } from '../../core/auth/session.service';
import { ToastService } from '../../core/services/toast.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { IconComponent } from '../../shared/components/icon/icon.component';
import { JsonViewerComponent } from '../../shared/components/json-viewer/json-viewer.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import {
  ScatterChartComponent,
  ScatterPoint,
} from '../../shared/components/scatter-chart/scatter-chart.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-optimiser-page',
  imports: [
    ReactiveFormsModule,
    DatePipe,
    DecimalPipe,
    CurrencyPipe,
    PercentPipe,
    IconComponent,
    StatusBadgeComponent,
    ScatterChartComponent,
    JsonViewerComponent,
    EmptyStateComponent,
    LoadingStateComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './optimiser.page.html',
  styleUrl: './optimiser.page.scss',
})
export class OptimiserPage {
  private readonly api = inject(ApiService);
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly session = inject(SessionService);
  private readonly route = inject(ActivatedRoute);
  private readonly toasts = inject(ToastService);
  private readonly destroyRef = inject(DestroyRef);
  private pollSubscription?: Subscription;

  readonly labels = AGENT_LABELS;
  readonly agent = signal<AgentType>('client_summary');
  readonly loading = signal(true);
  readonly starting = signal(false);
  readonly activatingVersion = signal('');
  readonly activePrompt = signal<PromptVersionResponse | null>(null);
  readonly versions = signal<PromptVersionResponse[]>([]);
  readonly jobs = signal<OptimisationJobResponse[]>([]);
  readonly results = signal<OptimisationResultResponse[]>([]);
  readonly currentJob = signal<OptimisationJobResponse | null>(null);
  readonly selectedResult = signal<OptimisationResultResponse | null>(null);
  readonly selectedCandidate = signal<OptimisationCandidateResponse | null>(null);

  readonly form = this.fb.group({
    advisorId: this.fb.control(this.session.advisorId(), { validators: [Validators.required] }),
    maxVariants: this.fb.control(3, {
      validators: [Validators.required, Validators.min(1), Validators.max(5)],
    }),
    benchmarkLimit: this.fb.control(3, { validators: [Validators.required, Validators.min(1)] }),
    repetitions: this.fb.control(2, {
      validators: [Validators.required, Validators.min(1), Validators.max(5)],
    }),
  });

  readonly agentJobs = computed(() => this.jobs().filter((job) => job.agent_type === this.agent()));
  readonly runningJobs = computed(() =>
    this.agentJobs().filter((job) => job.status === 'queued' || job.status === 'running'),
  );
  readonly scatterPoints = computed<ScatterPoint[]>(() => {
    const result = this.selectedResult();
    if (!result) return [];
    return [
      {
        label: `Baseline · ${result.baseline.version}`,
        x: result.baseline.metrics.latency_ms,
        y: result.baseline.metrics.quality,
        status: 'baseline',
        detail: `${result.baseline.metrics.sample_count} samples`,
      },
      ...result.candidates.map((candidate) => ({
        label: candidate.version,
        x: candidate.metrics.latency_ms,
        y: candidate.metrics.quality,
        status: candidate.selected ? 'selected' : candidate.status,
        detail: candidate.qualifies ? 'Policy-qualified' : 'Did not qualify',
      })),
    ];
  });

  constructor() {
    const agent = this.route.snapshot.queryParamMap.get('agent');
    if (this.isAgentType(agent)) this.agent.set(agent);
    this.load();
  }

  changeAgent(value: string): void {
    if (!this.isAgentType(value) || value === this.agent()) return;
    this.agent.set(value);
    this.currentJob.set(null);
    this.selectedResult.set(null);
    this.selectedCandidate.set(null);
    this.pollSubscription?.unsubscribe();
    this.load();
  }

  load(): void {
    this.loading.set(true);
    const agent = this.agent();
    forkJoin({
      active: this.api.getActivePrompt(agent).pipe(catchError(() => of(null))),
      versions: this.api.getPromptVersions(agent, { pageSize: 200 }),
      jobs: this.api.getOptimisations({ page: 1, pageSize: 100 }),
      results: this.api.getOptimisationResults({ page: 1, pageSize: 50, agentType: agent }),
    })
      .pipe(
        finalize(() => this.loading.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((data) => {
        this.activePrompt.set(data.active);
        this.versions.set(data.versions.items);
        this.jobs.set(data.jobs.items);
        this.results.set(data.results.items);
        const selected = this.selectedResult();
        const latest = selected
          ? (data.results.items.find((item) => item.optimisation_id === selected.optimisation_id) ??
            data.results.items[0])
          : data.results.items[0];
        if (latest) this.selectResult(latest);
        const activeJob = data.jobs.items.find(
          (job) =>
            job.agent_type === agent && (job.status === 'queued' || job.status === 'running'),
        );
        if (activeJob) this.trackJob(activeJob);
      });
  }

  startOptimisation(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    this.session.setAdvisorId(value.advisorId);
    this.starting.set(true);
    this.api
      .createOptimisation(this.agent(), {
        advisor_id: value.advisorId.trim(),
        max_variants: value.maxVariants,
        benchmark_limit: value.benchmarkLimit,
        repetitions: value.repetitions,
      })
      .pipe(
        finalize(() => this.starting.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((job) => {
        this.currentJob.set(job);
        this.jobs.update((items) => [job, ...items.filter((item) => item.job_id !== job.job_id)]);
        this.toasts.info(
          'Optimisation queued',
          `Job ${job.job_id.slice(0, 8)} will run asynchronously.`,
        );
        this.pollJob(job.job_id);
      });
  }

  trackJob(job: OptimisationJobResponse): void {
    this.currentJob.set(job);
    if (job.status === 'queued' || job.status === 'running') this.pollJob(job.job_id);
    else if (job.status === 'completed' && job.result_id) this.loadResult(job.result_id);
  }

  selectResult(result: OptimisationResultResponse): void {
    this.selectedResult.set(result);
    const candidate =
      result.candidates.find((item) => item.selected) ?? result.candidates[0] ?? null;
    this.selectedCandidate.set(candidate);
  }

  selectCandidate(candidate: OptimisationCandidateResponse): void {
    this.selectedCandidate.set(candidate);
  }

  activate(candidate: OptimisationCandidateResponse): void {
    const prompt = this.version(candidate.version);
    if (!prompt || candidate.status !== 'selected') return;
    this.activatePrompt(prompt);
  }

  activatePrompt(prompt: PromptVersionResponse): void {
    if (prompt.status !== 'selected' || prompt.is_active) return;
    if (
      !window.confirm(
        `Activate ${prompt.version} for ${this.labels[this.agent()]}? The currently active prompt will be replaced.`,
      )
    )
      return;
    this.activatingVersion.set(prompt.version);
    this.api
      .activatePrompt(this.agent(), prompt.version)
      .pipe(
        finalize(() => this.activatingVersion.set('')),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((response) => {
        this.activePrompt.set(response.prompt);
        this.versions.update((items) =>
          items.map((item) => ({
            ...item,
            is_active: item.version === response.prompt.version,
            activated_at:
              item.version === response.prompt.version
                ? response.prompt.activated_at
                : item.activated_at,
          })),
        );
        this.toasts.success(
          'Prompt activated',
          `${prompt.version} is now the default for new ${this.labels[this.agent()]} runs.`,
        );
      });
  }

  version(version: string): PromptVersionResponse | null {
    return this.versions().find((item) => item.version === version) ?? null;
  }

  baselinePrompt(): PromptVersionResponse | null {
    const result = this.selectedResult();
    return result ? this.version(result.baseline.version) : null;
  }

  candidatePrompt(): PromptVersionResponse | null {
    const candidate = this.selectedCandidate();
    return candidate ? this.version(candidate.version) : null;
  }

  delta(value: number, baseline: number): number {
    return value - baseline;
  }

  ratioDelta(value: number, baseline: number): number {
    return baseline ? value / baseline - 1 : 0;
  }

  shortId(value: string): string {
    return value.length > 12 ? `${value.slice(0, 10)}…` : value;
  }

  private pollJob(jobId: string): void {
    this.pollSubscription?.unsubscribe();
    this.pollSubscription = timer(0, environment.optimisationPollIntervalMs)
      .pipe(
        switchMap(() => this.api.getOptimisation(jobId)),
        tap((job) => {
          this.currentJob.set(job);
          this.jobs.update((items) => [job, ...items.filter((item) => item.job_id !== job.job_id)]);
        }),
        takeWhile((job) => job.status === 'queued' || job.status === 'running', true),
        finalize(() => {
          const job = this.currentJob();
          if (job?.status === 'completed' && job.result_id) {
            this.loadResult(job.result_id);
            this.toasts.success(
              'Optimisation completed',
              'Candidate prompts are ready for review. No prompt was activated automatically.',
            );
          } else if (job?.status === 'failed') {
            this.toasts.error(
              'Optimisation failed',
              job.error_message || 'Review the job error and provider configuration.',
            );
          }
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();
  }

  private loadResult(resultId: number): void {
    this.api
      .getOptimisationResult(resultId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((result) => {
        this.results.update((items) => [
          result,
          ...items.filter((item) => item.optimisation_id !== result.optimisation_id),
        ]);
        this.selectResult(result);
        this.api
          .getPromptVersions(this.agent(), { pageSize: 200 })
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe((page) => this.versions.set(page.items));
      });
  }

  private isAgentType(value: string | null): value is AgentType {
    return value === 'client_summary' || value === 'meeting_notes' || value === 'investment_review';
  }
}
