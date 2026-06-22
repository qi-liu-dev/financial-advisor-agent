import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { DecimalPipe } from '@angular/common';

export interface ScatterPoint {
  label: string;
  x: number;
  y: number;
  status: string;
  detail?: string;
}

@Component({
  selector: 'app-scatter-chart',
  imports: [DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="chart-wrap">
      <svg viewBox="0 0 680 360" role="img" [attr.aria-label]="title">
        <line x1="68" y1="300" x2="650" y2="300" class="axis" />
        <line x1="68" y1="28" x2="68" y2="300" class="axis" />
        @for (tick of [0, 1, 2, 3, 4]; track tick) {
          <line
            x1="68"
            [attr.y1]="300 - tick * 68"
            x2="650"
            [attr.y2]="300 - tick * 68"
            class="grid"
          />
          <text x="58" [attr.y]="304 - tick * 68" text-anchor="end">
            {{ yTick(tick) | number: '1.1-1' }}
          </text>
        }
        @for (tick of [0, 1, 2, 3, 4]; track tick) {
          <text [attr.x]="68 + tick * 145.5" y="322" text-anchor="middle">
            {{ xTick(tick) | number: '1.0-0' }}
          </text>
        }
        @for (point of points; track point.label) {
          <g class="point" [attr.data-status]="point.status">
            <circle [attr.cx]="xPosition(point.x)" [attr.cy]="yPosition(point.y)" r="8">
              <title>{{ point.label }} — {{ point.detail || point.status }}</title>
            </circle>
            <text [attr.x]="xPosition(point.x) + 11" [attr.y]="yPosition(point.y) - 9">
              {{ point.label }}
            </text>
          </g>
        }
        <text x="359" y="350" text-anchor="middle" class="label">{{ xLabel }}</text>
        <text x="15" y="165" text-anchor="middle" transform="rotate(-90 15 165)" class="label">
          {{ yLabel }}
        </text>
      </svg>
      @if (!points.length) {
        <div class="empty">No candidate metrics to plot.</div>
      }
    </div>
  `,
  styles: [
    `
      .chart-wrap {
        position: relative;
        min-height: 20rem;
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        background: var(--surface-raised);
        overflow: hidden;
      }
      svg {
        display: block;
        width: 100%;
        height: auto;
        min-height: 20rem;
      }
      .axis {
        stroke: var(--border-strong);
        stroke-width: 1.2;
      }
      .grid {
        stroke: var(--border);
        stroke-dasharray: 4 5;
      }
      text {
        fill: var(--text-subtle);
        font-size: 11px;
        font-family: var(--font-sans);
      }
      .label {
        font-weight: 700;
      }
      .point circle {
        fill: var(--blue);
        stroke: var(--surface);
        stroke-width: 3;
      }
      .point[data-status='baseline'] circle {
        fill: var(--text-muted);
      }
      .point[data-status='selected'] circle {
        fill: var(--success);
      }
      .point[data-status='rejected'] circle {
        fill: var(--danger);
      }
      .point text {
        fill: var(--text);
        font-weight: 700;
      }
      .empty {
        position: absolute;
        inset: 0;
        display: grid;
        place-items: center;
        color: var(--text-subtle);
        font-size: 0.85rem;
      }
    `,
  ],
})
export class ScatterChartComponent {
  @Input() points: ScatterPoint[] = [];
  @Input() title = 'Prompt quality versus latency';
  @Input() xLabel = 'Latency (ms)';
  @Input() yLabel = 'Quality (1–5)';

  private xRange(): [number, number] {
    if (!this.points.length) return [0, 1];
    const values = this.points.map((point) => point.x);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * 0.12, max * 0.05, 1);
    return [Math.max(0, min - padding), max + padding];
  }

  private yRange(): [number, number] {
    if (!this.points.length) return [0, 5];
    const values = this.points.map((point) => point.y);
    const min = Math.max(0, Math.min(...values) - 0.25);
    const max = Math.min(5, Math.max(...values) + 0.25);
    return max === min ? [Math.max(0, min - 0.5), Math.min(5, max + 0.5)] : [min, max];
  }

  xPosition(value: number): number {
    const [min, max] = this.xRange();
    return 68 + ((value - min) / (max - min || 1)) * 582;
  }
  yPosition(value: number): number {
    const [min, max] = this.yRange();
    return 300 - ((value - min) / (max - min || 1)) * 272;
  }
  xTick(tick: number): number {
    const [min, max] = this.xRange();
    return min + ((max - min) / 4) * tick;
  }
  yTick(tick: number): number {
    const [min, max] = this.yRange();
    return min + ((max - min) / 4) * tick;
  }
}
