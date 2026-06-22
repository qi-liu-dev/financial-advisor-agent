import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { catchError, interval, of, startWith, switchMap } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { ApiService } from '../core/api/api.service';
import { HealthResponse } from '../core/api/api.models';
import { SessionService } from '../core/auth/session.service';
import { ThemeService } from '../core/services/theme.service';
import { IconComponent, IconName } from '../shared/components/icon/icon.component';
import { StatusBadgeComponent } from '../shared/components/status-badge/status-badge.component';
import { ToastOutletComponent } from '../shared/components/toast-outlet/toast-outlet.component';

interface NavItem {
  label: string;
  description: string;
  route: string;
  icon: IconName;
  exact?: boolean;
}

@Component({
  selector: 'app-shell',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    IconComponent,
    StatusBadgeComponent,
    ToastOutletComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app-shell.component.html',
  styleUrl: './app-shell.component.scss',
})
export class AppShellComponent {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  readonly session = inject(SessionService);
  readonly theme = inject(ThemeService);
  readonly menuOpen = signal(false);
  readonly health = signal<HealthResponse | null>(null);
  readonly healthReachable = signal(false);

  readonly navItems: NavItem[] = [
    {
      label: 'Overview',
      description: 'System performance',
      route: '/',
      icon: 'dashboard',
      exact: true,
    },
    {
      label: 'Benchmark Tasks',
      description: 'Synthetic test library',
      route: '/tasks',
      icon: 'tasks',
    },
    {
      label: 'Agent Playground',
      description: 'Run structured agents',
      route: '/playground',
      icon: 'playground',
    },
    {
      label: 'Run Evaluation',
      description: 'Inspect and score runs',
      route: '/runs',
      icon: 'runs',
    },
    {
      label: 'Prompt Optimizer',
      description: 'Compare prompt versions',
      route: '/optimiser',
      icon: 'optimiser',
    },
    {
      label: 'Advisor Preferences',
      description: 'Personalisation and data',
      route: '/preferences',
      icon: 'preferences',
    },
  ];

  constructor() {
    interval(60_000)
      .pipe(
        startWith(0),
        switchMap(() => this.api.getHealth().pipe(catchError(() => of(null)))),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((health) => {
        this.health.set(health);
        this.healthReachable.set(health !== null);
      });
  }

  closeMenu(): void {
    this.menuOpen.set(false);
  }
}
