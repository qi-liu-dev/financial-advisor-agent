import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    title: 'Overview · Advisor Agent Lab',
    loadComponent: () => import('./features/dashboard/dashboard.page').then((m) => m.DashboardPage),
  },
  {
    path: 'tasks',
    title: 'Benchmark Tasks · Advisor Agent Lab',
    loadComponent: () => import('./features/tasks/tasks.page').then((m) => m.TasksPage),
  },
  {
    path: 'playground',
    title: 'Agent Playground · Advisor Agent Lab',
    loadComponent: () =>
      import('./features/agent-runner/agent-runner.page').then((m) => m.AgentRunnerPage),
  },
  {
    path: 'runs',
    title: 'Run Evaluation · Advisor Agent Lab',
    loadComponent: () =>
      import('./features/runs/run-evaluation.page').then((m) => m.RunEvaluationPage),
  },
  {
    path: 'optimiser',
    title: 'Prompt Optimizer · Advisor Agent Lab',
    loadComponent: () => import('./features/optimiser/optimiser.page').then((m) => m.OptimiserPage),
  },
  {
    path: 'preferences',
    title: 'Advisor Preferences · Advisor Agent Lab',
    loadComponent: () =>
      import('./features/preferences/preferences.page').then((m) => m.PreferencesPage),
  },
  { path: '**', redirectTo: '' },
];
