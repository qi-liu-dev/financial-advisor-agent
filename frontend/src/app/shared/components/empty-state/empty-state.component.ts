import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { IconComponent, IconName } from '../icon/icon.component';

@Component({
  selector: 'app-empty-state',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div class="empty">
    <div><app-icon [name]="icon" /></div>
    <h3>{{ title }}</h3>
    <p>{{ message }}</p>
    <ng-content />
  </div>`,
  styles: [
    `
      .empty {
        display: grid;
        justify-items: center;
        text-align: center;
        padding: 3rem 1.5rem;
        color: var(--text-muted);
      }
      .empty > div {
        display: grid;
        place-items: center;
        width: 3rem;
        height: 3rem;
        border-radius: 1rem;
        background: var(--teal-soft);
        color: var(--teal);
      }
      app-icon {
        width: 1.45rem;
        height: 1.45rem;
      }
      h3 {
        margin: 0.9rem 0 0.35rem;
        color: var(--text);
        font-size: 1rem;
      }
      p {
        max-width: 28rem;
        margin: 0 0 1rem;
        color: var(--text-subtle);
        font-size: 0.83rem;
        line-height: 1.55;
      }
    `,
  ],
})
export class EmptyStateComponent {
  @Input() title = 'Nothing here yet';
  @Input() message = 'Data will appear here when it becomes available.';
  @Input() icon: IconName = 'flask';
}
