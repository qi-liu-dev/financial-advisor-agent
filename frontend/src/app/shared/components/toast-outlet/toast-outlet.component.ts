import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { ToastService } from '../../../core/services/toast.service';
import { IconComponent } from '../icon/icon.component';

@Component({
  selector: 'app-toast-outlet',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="toasts" aria-live="polite">
      @for (toast of toasts.messages(); track toast.id) {
        <article class="toast" [attr.data-tone]="toast.tone">
          <div class="mark">
            <app-icon
              [name]="
                toast.tone === 'success' ? 'check' : toast.tone === 'error' ? 'alert' : 'server'
              "
            />
          </div>
          <div>
            <strong>{{ toast.title }}</strong>
            @if (toast.message) {
              <p>{{ toast.message }}</p>
            }
          </div>
          <button
            type="button"
            aria-label="Dismiss notification"
            (click)="toasts.dismiss(toast.id)"
          >
            <app-icon name="close" />
          </button>
        </article>
      }
    </div>
  `,
  styles: [
    `
      .toasts {
        position: fixed;
        z-index: 1000;
        right: 1.25rem;
        bottom: 1.25rem;
        display: grid;
        gap: 0.65rem;
        width: min(25rem, calc(100vw - 2rem));
      }
      .toast {
        display: grid;
        grid-template-columns: auto 1fr auto;
        gap: 0.75rem;
        align-items: start;
        padding: 0.9rem 1rem;
        border: 1px solid var(--border);
        border-left: 4px solid var(--blue);
        border-radius: var(--radius-md);
        background: var(--surface);
        box-shadow: var(--shadow-lg);
        animation: enter 0.18s ease-out;
      }
      .toast[data-tone='success'] {
        border-left-color: var(--success);
      }
      .toast[data-tone='error'] {
        border-left-color: var(--danger);
      }
      .toast[data-tone='warning'] {
        border-left-color: var(--warning);
      }
      .mark {
        display: grid;
        place-items: center;
        width: 1.8rem;
        height: 1.8rem;
        border-radius: 50%;
        background: var(--blue-soft);
        color: var(--blue);
      }
      .toast[data-tone='success'] .mark {
        background: var(--success-soft);
        color: var(--success);
      }
      .toast[data-tone='error'] .mark {
        background: var(--danger-soft);
        color: var(--danger);
      }
      .toast[data-tone='warning'] .mark {
        background: var(--warning-soft);
        color: var(--warning);
      }
      strong {
        display: block;
        color: var(--text);
        font-size: 0.84rem;
      }
      p {
        margin: 0.18rem 0 0;
        color: var(--text-muted);
        font-size: 0.76rem;
        line-height: 1.45;
      }
      button {
        border: 0;
        background: transparent;
        color: var(--text-subtle);
        cursor: pointer;
        padding: 0.2rem;
      }
      button app-icon {
        width: 1rem;
        height: 1rem;
      }
      @keyframes enter {
        from {
          opacity: 0;
          transform: translateY(0.5rem);
        }
        to {
          opacity: 1;
          transform: none;
        }
      }
    `,
  ],
})
export class ToastOutletComponent {
  readonly toasts = inject(ToastService);
}
