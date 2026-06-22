import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { ApiService } from '../../core/api/api.service';
import {
  AGENT_LABELS,
  AgentType,
  BenchmarkDifficulty,
  BenchmarkTaskResponse,
} from '../../core/api/api.models';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { IconComponent } from '../../shared/components/icon/icon.component';
import { JsonViewerComponent } from '../../shared/components/json-viewer/json-viewer.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-tasks-page',
  imports: [
    FormsModule,
    RouterLink,
    IconComponent,
    JsonViewerComponent,
    StatusBadgeComponent,
    EmptyStateComponent,
    LoadingStateComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './tasks.page.html',
  styleUrl: './tasks.page.scss',
})
export class TasksPage {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);

  readonly loading = signal(true);
  readonly tasks = signal<BenchmarkTaskResponse[]>([]);
  readonly selectedTask = signal<BenchmarkTaskResponse | null>(null);
  readonly search = signal('');
  readonly agentFilter = signal<AgentType | ''>('');
  readonly difficultyFilter = signal<BenchmarkDifficulty | ''>('');
  readonly tagFilter = signal('');
  readonly labels = AGENT_LABELS;

  readonly tags = computed(() =>
    Array.from(new Set(this.tasks().flatMap((task) => task.tags))).sort(),
  );
  readonly filteredTasks = computed(() => {
    const query = this.search().trim().toLowerCase();
    return this.tasks().filter((task) => {
      const matchesSearch =
        !query ||
        [task.task_id, task.agent_type, task.difficulty, ...task.tags]
          .join(' ')
          .toLowerCase()
          .includes(query);
      return (
        matchesSearch &&
        (!this.agentFilter() || task.agent_type === this.agentFilter()) &&
        (!this.difficultyFilter() || task.difficulty === this.difficultyFilter()) &&
        (!this.tagFilter() || task.tags.includes(this.tagFilter()))
      );
    });
  });

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api
      .getTasks()
      .pipe(
        finalize(() => this.loading.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((tasks) => {
        this.tasks.set(tasks);
        const current = this.selectedTask();
        this.selectedTask.set(
          current
            ? (tasks.find((task) => task.task_id === current.task_id) ?? tasks[0] ?? null)
            : (tasks[0] ?? null),
        );
      });
  }

  select(task: BenchmarkTaskResponse): void {
    this.selectedTask.set(task);
  }

  clearFilters(): void {
    this.search.set('');
    this.agentFilter.set('');
    this.difficultyFilter.set('');
    this.tagFilter.set('');
  }

  expectationCount(task: BenchmarkTaskResponse): number {
    return (
      task.expected.must_mention.length +
      task.expected.must_not_mention.length +
      task.expected.required_citations.length
    );
  }
}
