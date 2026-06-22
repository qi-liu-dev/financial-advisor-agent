import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { PageMetadata } from '../../../core/api/api.models';
import { IconComponent } from '../icon/icon.component';

@Component({
  selector: 'app-pagination',
  imports: [IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav class="pagination" aria-label="Pagination">
      <p>{{ rangeStart() }}–{{ rangeEnd() }} of {{ page.total_items }}</p>
      <div>
        <button
          class="icon-button"
          type="button"
          aria-label="Previous page"
          [disabled]="page.page <= 1"
          (click)="pageChange.emit(page.page - 1)"
        >
          <app-icon name="chevron-left" />
        </button>
        <span>Page {{ page.page }} of {{ page.total_pages || 1 }}</span>
        <button
          class="icon-button"
          type="button"
          aria-label="Next page"
          [disabled]="page.page >= page.total_pages"
          (click)="pageChange.emit(page.page + 1)"
        >
          <app-icon name="chevron-right" />
        </button>
      </div>
    </nav>
  `,
  styles: [
    `
      .pagination {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding-top: 1rem;
        color: var(--text-subtle);
        font-size: 0.8rem;
      }
      .pagination p {
        margin: 0;
      }
      .pagination div {
        display: flex;
        align-items: center;
        gap: 0.65rem;
      }
      .icon-button {
        display: grid;
        place-items: center;
        width: 2rem;
        height: 2rem;
        border: 1px solid var(--border);
        border-radius: 0.5rem;
        background: var(--surface);
        color: var(--text-muted);
        cursor: pointer;
      }
      .icon-button:disabled {
        opacity: 0.35;
        cursor: not-allowed;
      }
      .icon-button:not(:disabled):hover {
        background: var(--surface-hover);
        color: var(--text);
      }
      app-icon {
        width: 1rem;
        height: 1rem;
      }
      @media (max-width: 560px) {
        .pagination {
          align-items: flex-start;
          flex-direction: column;
        }
      }
    `,
  ],
})
export class PaginationComponent {
  @Input({ required: true }) page!: PageMetadata;
  @Output() pageChange = new EventEmitter<number>();
  rangeStart(): number {
    return this.page.total_items ? (this.page.page - 1) * this.page.page_size + 1 : 0;
  }
  rangeEnd(): number {
    return Math.min(this.page.page * this.page.page_size, this.page.total_items);
  }
}
