import { CurrencyPipe, DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize, forkJoin } from 'rxjs';

import { ApiService } from '../../core/api/api.service';
import {
  AdvisorMemoryResponse,
  AdvisorPreferences,
  ClientProfileData,
  ClientWorkspaceResponse,
  MockDataItem,
} from '../../core/api/api.models';
import { SessionService } from '../../core/auth/session.service';
import { ToastService } from '../../core/services/toast.service';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { IconComponent } from '../../shared/components/icon/icon.component';
import { JsonViewerComponent } from '../../shared/components/json-viewer/json-viewer.component';
import { LoadingStateComponent } from '../../shared/components/loading-state/loading-state.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';

@Component({
  selector: 'app-preferences-page',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    DatePipe,
    CurrencyPipe,
    DecimalPipe,
    IconComponent,
    StatusBadgeComponent,
    JsonViewerComponent,
    EmptyStateComponent,
    LoadingStateComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './preferences.page.html',
  styleUrl: './preferences.page.scss',
})
export class PreferencesPage {
  private readonly api = inject(ApiService);
  private readonly fb = inject(NonNullableFormBuilder);
  readonly session = inject(SessionService);
  private readonly toasts = inject(ToastService);
  private readonly destroyRef = inject(DestroyRef);

  readonly loadingMemory = signal(false);
  readonly saving = signal(false);
  readonly deleting = signal(false);
  readonly memory = signal<AdvisorMemoryResponse | null>(null);
  readonly clients = signal<ClientProfileData[]>([]);
  readonly selectedClientId = signal('');
  readonly workspace = signal<ClientWorkspaceResponse | null>(null);
  readonly loadingWorkspace = signal(false);

  readonly preferencesForm = this.fb.group({
    advisorId: this.fb.control(this.session.advisorId(), { validators: [Validators.required] }),
    summaryStyle: this.fb.control<AdvisorPreferences['summary_style']>('balanced'),
    detailLevel: this.fb.control<AdvisorPreferences['detail_level']>('medium'),
    riskFocus: this.fb.control<AdvisorPreferences['risk_focus']>('balanced'),
    preferredLanguage: this.fb.control('en', { validators: [Validators.required] }),
  });

  readonly connectionForm = this.fb.group({
    apiKey: this.fb.control(this.session.apiKey()),
  });

  constructor() {
    this.loadInitial();
  }

  loadMemory(): void {
    const advisorId = this.preferencesForm.controls.advisorId.value.trim();
    if (!advisorId) {
      this.preferencesForm.controls.advisorId.markAsTouched();
      return;
    }
    this.loadingMemory.set(true);
    this.api
      .getMemory(advisorId)
      .pipe(
        finalize(() => this.loadingMemory.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((memory) => {
        this.memory.set(memory);
        this.session.setAdvisorId(memory.advisor_id);
        this.patchPreferences(memory.preferences);
      });
  }

  savePreferences(): void {
    if (this.preferencesForm.invalid) {
      this.preferencesForm.markAllAsTouched();
      return;
    }
    const value = this.preferencesForm.getRawValue();
    const preferences: AdvisorPreferences = {
      summary_style: value.summaryStyle,
      detail_level: value.detailLevel,
      risk_focus: value.riskFocus,
      preferred_language: value.preferredLanguage.trim().toLowerCase() || 'en',
    };
    this.session.setAdvisorId(value.advisorId);
    this.saving.set(true);
    this.api
      .updateMemory(value.advisorId.trim(), preferences)
      .pipe(
        finalize(() => this.saving.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((memory) => {
        this.memory.set(memory);
        this.toasts.success(
          'Advisor preferences saved',
          'New agent runs can use these defaults when no request-level preferences are supplied.',
        );
      });
  }

  deletePreferences(): void {
    const advisorId = this.preferencesForm.controls.advisorId.value.trim();
    if (!advisorId || !window.confirm(`Delete stored preferences for ${advisorId}?`)) return;
    this.deleting.set(true);
    this.api
      .deleteMemory(advisorId)
      .pipe(
        finalize(() => this.deleting.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(() => {
        this.memory.set(null);
        this.patchPreferences({
          summary_style: 'balanced',
          detail_level: 'medium',
          risk_focus: 'balanced',
          preferred_language: 'en',
        });
        this.toasts.success('Advisor memory deleted');
      });
  }

  saveConnection(): void {
    this.session.setApiKey(this.connectionForm.controls.apiKey.value);
    this.toasts.success(
      this.session.apiKey() ? 'API credential stored for this tab' : 'API credential cleared',
      this.session.apiKey()
        ? 'It is kept in sessionStorage and sent as X-API-Key to API requests.'
        : undefined,
    );
  }

  chooseClient(clientId: string): void {
    this.selectedClientId.set(clientId);
    if (!clientId) {
      this.workspace.set(null);
      return;
    }
    this.loadingWorkspace.set(true);
    this.api
      .getClientWorkspace(clientId)
      .pipe(
        finalize(() => this.loadingWorkspace.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((workspace) => this.workspace.set(workspace));
  }

  allocationEntries(allocation: Record<string, number>): Array<{ name: string; value: number }> {
    return Object.entries(allocation)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }

  private loadInitial(): void {
    this.loadingMemory.set(true);
    forkJoin({
      memory: this.api.getMemory(this.session.advisorId()),
      clients: this.api.getMockData('clients'),
    })
      .pipe(
        finalize(() => this.loadingMemory.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(({ memory, clients }) => {
        this.memory.set(memory);
        this.patchPreferences(memory.preferences);
        const clientItems = clients.items.filter((item): item is ClientProfileData =>
          this.isClient(item),
        );
        this.clients.set(clientItems);
        if (clientItems[0]) this.chooseClient(clientItems[0].client_id);
      });
  }

  private patchPreferences(preferences: AdvisorPreferences): void {
    this.preferencesForm.patchValue({
      summaryStyle: preferences.summary_style,
      detailLevel: preferences.detail_level,
      riskFocus: preferences.risk_focus,
      preferredLanguage: preferences.preferred_language,
    });
  }

  private isClient(item: MockDataItem): item is ClientProfileData {
    return 'risk_tolerance' in item && 'goals' in item;
  }
}
