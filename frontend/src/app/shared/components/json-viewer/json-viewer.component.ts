import { ChangeDetectionStrategy, Component, Input, inject, signal } from '@angular/core';
import { IconComponent } from '../icon/icon.component';
import { ToastService } from '../../../core/services/toast.service';

@Component({
  selector: 'app-json-viewer',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="json-viewer">
      <header>
        <button type="button" class="toggle" (click)="collapsed.update((v) => !v)">
          <app-icon [name]="collapsed() ? 'chevron-right' : 'chevron-left'" />
          {{ title }}
        </button>
        <button type="button" class="icon-button" aria-label="Copy JSON" (click)="copy()">
          <app-icon name="copy" />
        </button>
      </header>
      @if (!collapsed()) {
        <pre>{{ formatted }}</pre>
      }
    </section>
  `,
  styles: [
    `
      .json-viewer {
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        overflow: hidden;
        background: var(--code-bg);
      }
      header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.55rem 0.7rem;
        border-bottom: 1px solid var(--border);
        background: var(--surface-raised);
      }
      .toggle,
      .icon-button {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        border: 0;
        background: transparent;
        color: var(--text-muted);
        font: inherit;
        font-size: 0.78rem;
        font-weight: 700;
        cursor: pointer;
      }
      .toggle app-icon {
        width: 0.9rem;
        height: 0.9rem;
        transform: rotate(-90deg);
      }
      .icon-button {
        padding: 0.35rem;
        border-radius: 0.4rem;
      }
      .icon-button:hover {
        background: var(--surface-hover);
        color: var(--text);
      }
      pre {
        margin: 0;
        padding: 1rem;
        max-height: 30rem;
        overflow: auto;
        font-family: var(--font-mono);
        font-size: 0.76rem;
        line-height: 1.6;
        color: var(--code-text);
        white-space: pre-wrap;
        word-break: break-word;
      }
    `,
  ],
})
export class JsonViewerComponent {
  private readonly toasts = inject(ToastService);
  @Input({ required: true }) data: unknown;
  @Input() title = 'Raw JSON';
  @Input() startCollapsed = true;
  readonly collapsed = signal(true);

  ngOnInit(): void {
    this.collapsed.set(this.startCollapsed);
  }

  get formatted(): string {
    return JSON.stringify(this.data, null, 2);
  }

  async copy(): Promise<void> {
    await navigator.clipboard.writeText(this.formatted);
    this.toasts.success('Copied', 'JSON copied to the clipboard.');
  }
}
