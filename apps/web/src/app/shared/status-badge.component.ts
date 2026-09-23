import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import type { StatusTone } from './ux-foundation.types';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span
    class="ux-status"
    [class]="'ux-status tone-' + tone()"
    [attr.data-status]="status()"
    [title]="tooltip()"
    >{{ label() }}</span
  >`,
  styles: `
    :host {
      display: inline-block;
    }
    .ux-status {
      display: inline-flex;
      align-items: center;
      min-height: 1.6rem;
      padding: 0.18rem 0.55rem;
      border: 1px solid currentColor;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }
    .tone-neutral {
      color: var(--vj-color-muted);
      background: var(--vj-color-surface-muted);
    }
    .tone-info {
      color: var(--vj-color-info);
      background: #e9f3f8;
    }
    .tone-success {
      color: var(--vj-color-success);
      background: #e9f6ef;
    }
    .tone-warning {
      color: var(--vj-color-warning);
      background: #fff4df;
    }
    .tone-danger {
      color: var(--vj-color-error);
      background: #fdecec;
    }
  `,
})
export class StatusBadgeComponent {
  readonly status = input.required<string>();
  readonly label = input('');
  readonly tone = input<StatusTone>('neutral');
  readonly tooltip = computed(() => `Status: ${this.status()}`);
}
