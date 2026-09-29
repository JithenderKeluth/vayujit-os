import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import type { StatusTone } from './ux-foundation.types';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span
    class="ux-status vj-status-badge"
    [class]="'ux-status vj-status-badge tone-' + tone()"
    [attr.data-status]="status()"
    [attr.aria-label]="displayLabel()"
    [title]="tooltip()"
    >{{ displayLabel() }}</span
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
  readonly displayLabel = computed(() => {
    const value = this.label() || this.status();
    if (!/^[A-Z0-9_ -]+$/.test(value)) return value;
    const labels: Record<string, string> = {
      PENDING_REVIEW: 'Needs review',
      WAITING_FOR_APPROVAL: 'Waiting for approval',
      RETRYABLE: 'Ready to retry',
      FAILED: 'Failed',
      BLOCKED: 'Blocked',
      COMPLETED: 'Complete',
      SUCCEEDED: 'Complete',
      READY: 'Ready',
      IN_PROGRESS: 'In progress',
      REVIEW_REQUIRED: 'Needs review',
    };
    return labels[value] ?? value;
  });
  readonly tooltip = computed(() => `Status: ${this.status()}`);
}
