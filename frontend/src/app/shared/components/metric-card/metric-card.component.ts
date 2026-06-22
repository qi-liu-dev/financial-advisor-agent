import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { IconComponent, IconName } from '../icon/icon.component';

@Component({
  selector: 'app-metric-card',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <article class="metric-card">
      <div class="metric-card__icon" [attr.data-tone]="tone">
        <app-icon [name]="icon" />
      </div>
      <div>
        <p class="metric-card__label">{{ label }}</p>
        <p class="metric-card__value">{{ value }}</p>
        @if (helper) {
          <p class="metric-card__helper">{{ helper }}</p>
        }
      </div>
    </article>
  `,
  styleUrl: './metric-card.component.scss',
})
export class MetricCardComponent {
  @Input({ required: true }) label = '';
  @Input({ required: true }) value: string | number = '—';
  @Input() helper = '';
  @Input() icon: IconName = 'chart';
  @Input() tone: 'teal' | 'blue' | 'gold' | 'violet' = 'teal';
}
