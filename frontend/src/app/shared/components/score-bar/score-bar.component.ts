import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { MetricScore } from '../../../core/api/api.models';

@Component({
  selector: 'app-score-bar',
  imports: [DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="score-row">
      <div class="score-row__top">
        <span>{{ label }}</span
        ><strong>{{ metric.score | number: '1.1-1' }}/5</strong>
      </div>
      <div
        class="track"
        role="progressbar"
        [attr.aria-label]="label"
        [attr.aria-valuenow]="metric.score"
        aria-valuemin="1"
        aria-valuemax="5"
      >
        <span [style.width.%]="metric.score * 20" [attr.data-score]="metric.score"></span>
      </div>
      @if (showFeedback) {
        <p>{{ metric.feedback }}</p>
      }
    </div>
  `,
  styles: [
    `
      .score-row {
        display: grid;
        gap: 0.45rem;
      }
      .score-row__top {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        color: var(--text-muted);
        font-size: 0.82rem;
      }
      .score-row__top strong {
        color: var(--text);
        font-variant-numeric: tabular-nums;
      }
      .track {
        height: 0.48rem;
        border-radius: 999px;
        background: var(--neutral-soft);
        overflow: hidden;
      }
      .track span {
        display: block;
        height: 100%;
        border-radius: inherit;
        background: var(--teal);
        transition: width 0.35s ease;
      }
      .track span[data-score='1'],
      .track span[data-score='2'] {
        background: var(--danger);
      }
      .track span[data-score='3'] {
        background: var(--warning);
      }
      p {
        margin: 0;
        color: var(--text-subtle);
        font-size: 0.78rem;
        line-height: 1.5;
      }
    `,
  ],
})
export class ScoreBarComponent {
  @Input({ required: true }) label = '';
  @Input({ required: true }) metric!: MetricScore;
  @Input() showFeedback = false;
}
