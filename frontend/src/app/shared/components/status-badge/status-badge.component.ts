import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  selector: 'app-status-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="status" [attr.data-tone]="tone()"
    ><span class="dot"></span>{{ label || status }}</span
  >`,
  styles: [
    `
      .status {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        border-radius: 999px;
        padding: 0.27rem 0.62rem;
        font-size: 0.72rem;
        font-weight: 750;
        letter-spacing: 0.025em;
        text-transform: capitalize;
        background: var(--neutral-soft);
        color: var(--text-muted);
        white-space: nowrap;
      }
      .dot {
        width: 0.4rem;
        height: 0.4rem;
        border-radius: 50%;
        background: currentColor;
      }
      .status[data-tone='success'] {
        background: var(--success-soft);
        color: var(--success);
      }
      .status[data-tone='warning'] {
        background: var(--warning-soft);
        color: var(--warning);
      }
      .status[data-tone='danger'] {
        background: var(--danger-soft);
        color: var(--danger);
      }
      .status[data-tone='info'] {
        background: var(--blue-soft);
        color: var(--blue);
      }
      .status[data-tone='violet'] {
        background: var(--violet-soft);
        color: var(--violet);
      }
    `,
  ],
})
export class StatusBadgeComponent {
  @Input({ required: true }) status = '';
  @Input() label = '';

  tone(): string {
    const value = this.status.toLowerCase();
    if (['ok', 'completed', 'selected', 'active', 'evaluated', 'success'].includes(value))
      return 'success';
    if (['queued', 'candidate', 'degraded', 'pending'].includes(value)) return 'warning';
    if (['failed', 'rejected', 'error', 'unsafe'].includes(value)) return 'danger';
    if (['running', 'baseline'].includes(value)) return 'info';
    if (['admin'].includes(value)) return 'violet';
    return 'neutral';
  }
}
