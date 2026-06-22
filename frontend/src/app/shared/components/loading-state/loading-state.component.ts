import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

@Component({
  selector: 'app-loading-state',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div class="loading">
    <span></span>
    <p>{{ label }}</p>
  </div>`,
  styles: [
    `
      .loading {
        display: grid;
        place-items: center;
        gap: 0.8rem;
        padding: 3rem;
        color: var(--text-subtle);
        font-size: 0.82rem;
      }
      .loading span {
        width: 2rem;
        height: 2rem;
        border: 3px solid var(--border);
        border-top-color: var(--teal);
        border-radius: 50%;
        animation: spin 0.75s linear infinite;
      }
      .loading p {
        margin: 0;
      }
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
    `,
  ],
})
export class LoadingStateComponent {
  @Input() label = 'Loading…';
}
