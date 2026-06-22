import { Injectable, signal } from '@angular/core';

const ADVISOR_KEY = 'financial-advisor-dashboard.advisor-id';
const API_KEY = 'financial-advisor-dashboard.api-key';

@Injectable({ providedIn: 'root' })
export class SessionService {
  readonly advisorId = signal(this.readLocal(ADVISOR_KEY) || 'demo-advisor');
  readonly apiKey = signal(this.readSession(API_KEY));

  setAdvisorId(value: string): void {
    const resolved = value.trim() || 'demo-advisor';
    this.advisorId.set(resolved);
    localStorage.setItem(ADVISOR_KEY, resolved);
  }

  setApiKey(value: string): void {
    const resolved = value.trim();
    this.apiKey.set(resolved);
    if (resolved) sessionStorage.setItem(API_KEY, resolved);
    else sessionStorage.removeItem(API_KEY);
  }

  private readLocal(key: string): string {
    try {
      return localStorage.getItem(key) ?? '';
    } catch {
      return '';
    }
  }

  private readSession(key: string): string {
    try {
      return sessionStorage.getItem(key) ?? '';
    } catch {
      return '';
    }
  }
}
