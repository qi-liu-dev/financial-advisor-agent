import { DOCUMENT } from '@angular/common';
import { Injectable, inject, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);
  readonly dark = signal(this.initialTheme());

  constructor() {
    this.apply();
  }

  toggle(): void {
    this.dark.update((value) => !value);
    this.apply();
    localStorage.setItem('financial-advisor-dashboard.theme', this.dark() ? 'dark' : 'light');
  }

  private apply(): void {
    this.document.documentElement.dataset['theme'] = this.dark() ? 'dark' : 'light';
  }

  private initialTheme(): boolean {
    try {
      const saved = localStorage.getItem('financial-advisor-dashboard.theme');
      if (saved) return saved === 'dark';
    } catch {
      // Fall through to the browser preference.
    }
    return globalThis.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  }
}
