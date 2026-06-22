import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

export type IconName =
  | 'dashboard'
  | 'tasks'
  | 'playground'
  | 'runs'
  | 'optimiser'
  | 'preferences'
  | 'menu'
  | 'sun'
  | 'moon'
  | 'refresh'
  | 'arrow-right'
  | 'check'
  | 'alert'
  | 'close'
  | 'trash'
  | 'play'
  | 'flask'
  | 'server'
  | 'copy'
  | 'chevron-left'
  | 'chevron-right'
  | 'external'
  | 'shield'
  | 'clock'
  | 'coins'
  | 'chart';

@Component({
  selector: 'app-icon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      @switch (name) {
        @case ('dashboard') {
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="4" rx="1" />
          <rect x="14" y="11" width="7" height="10" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
        }
        @case ('tasks') {
          <path d="M9 5h10M9 12h10M9 19h10" />
          <path d="m3 5 1.5 1.5L7 3.5M3 12l1.5 1.5L7 10.5M3 19l1.5 1.5L7 17.5" />
        }
        @case ('playground') {
          <path d="M9 3h6M10 3v5l-5.5 9.5A2.3 2.3 0 0 0 6.5 21h11a2.3 2.3 0 0 0 2-3.5L14 8V3" />
          <path d="M7.5 15h9" />
        }
        @case ('runs') {
          <path d="M4 4h16v16H4z" />
          <path d="M8 9h8M8 13h6M8 17h4" />
        }
        @case ('optimiser') {
          <path
            d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"
          />
          <circle cx="12" cy="12" r="4" />
        }
        @case ('preferences') {
          <path d="M4 6h16M4 12h16M4 18h16" />
          <circle cx="9" cy="6" r="2" fill="var(--surface)" />
          <circle cx="15" cy="12" r="2" fill="var(--surface)" />
          <circle cx="8" cy="18" r="2" fill="var(--surface)" />
        }
        @case ('menu') {
          <path d="M4 6h16M4 12h16M4 18h16" />
        }
        @case ('sun') {
          <circle cx="12" cy="12" r="4" />
          <path
            d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41"
          />
        }
        @case ('moon') {
          <path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" />
        }
        @case ('refresh') {
          <path d="M20 11a8 8 0 1 0-2.34 5.66L20 14" />
          <path d="M20 6v5h-5" />
        }
        @case ('arrow-right') {
          <path d="M5 12h14M13 6l6 6-6 6" />
        }
        @case ('check') {
          <path d="m5 12 4 4L19 6" />
        }
        @case ('alert') {
          <path
            d="M10.3 3.7 2.6 17a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 3.7a2 2 0 0 0-3.4 0z"
          />
          <path d="M12 9v4M12 17h.01" />
        }
        @case ('close') {
          <path d="m6 6 12 12M18 6 6 18" />
        }
        @case ('trash') {
          <path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 11v6M14 11v6" />
        }
        @case ('play') {
          <path d="m8 5 11 7-11 7z" />
        }
        @case ('flask') {
          <path d="M9 3h6M10 3v6l-5 8.5A2.3 2.3 0 0 0 7 21h10a2.3 2.3 0 0 0 2-3.5L14 9V3" />
          <path d="M8 15h8" />
        }
        @case ('server') {
          <rect x="3" y="4" width="18" height="6" rx="2" />
          <rect x="3" y="14" width="18" height="6" rx="2" />
          <path d="M7 7h.01M7 17h.01" />
        }
        @case ('copy') {
          <rect x="9" y="9" width="11" height="11" rx="2" />
          <path d="M15 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h3" />
        }
        @case ('chevron-left') {
          <path d="m15 18-6-6 6-6" />
        }
        @case ('chevron-right') {
          <path d="m9 18 6-6-6-6" />
        }
        @case ('external') {
          <path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
        }
        @case ('shield') {
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <path d="m9 12 2 2 4-4" />
        }
        @case ('clock') {
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        }
        @case ('coins') {
          <ellipse cx="9" cy="6" rx="6" ry="3" />
          <path d="M3 6v4c0 1.7 2.7 3 6 3s6-1.3 6-3V6M3 10v4c0 1.7 2.7 3 6 3 1 0 2-.1 2.8-.4" />
          <path d="M15 12c3.3 0 6 1.3 6 3s-2.7 3-6 3-6-1.3-6-3" />
          <path d="M9 15v3c0 1.7 2.7 3 6 3s6-1.3 6-3v-3" />
        }
        @case ('chart') {
          <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
        }
      }
    </svg>
  `,
  styles: [
    `
      :host {
        display: inline-flex;
        width: 1.25rem;
        height: 1.25rem;
      }
      svg {
        width: 100%;
        height: 100%;
        display: block;
      }
    `,
  ],
})
export class IconComponent {
  @Input({ required: true }) name!: IconName;
}
