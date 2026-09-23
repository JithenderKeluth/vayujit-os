import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import type { EvidenceDetail } from './ux-foundation.types';

@Component({
  selector: 'app-evidence-card',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <article class="ux-evidence" [attr.data-classification]="classification()">
      <div class="heading">
        <div>
          <p class="eyebrow">Evidence</p>
          <h3>{{ title() }}</h3>
        </div>
        <span>{{ classification() }}</span>
      </div>
      <p>{{ summary() }}</p>
      <dl>
        @if (source()) {
          <div>
            <dt>Source</dt>
            <dd>{{ source() }}</dd>
          </div>
        }
        @if (observedAt()) {
          <div>
            <dt>Observed</dt>
            <dd>{{ observedAt() }}</dd>
          </div>
        }
      </dl>
      @if (details().length) {
        <details>
          <summary>Technical details</summary>
          <dl>
            @for (detail of details(); track detail.label) {
              <div>
                <dt>{{ detail.label }}</dt>
                <dd>{{ detail.value ?? 'Not available' }}</dd>
              </div>
            }
          </dl>
        </details>
      }
    </article>
  `,
  styles: `
    :host {
      display: block;
    }
    .ux-evidence {
      padding: var(--vj-space-4);
      border: 1px solid var(--vj-color-border);
      border-radius: var(--vj-radius-md);
      background: var(--vj-color-surface);
    }
    .heading {
      display: flex;
      justify-content: space-between;
      gap: var(--vj-space-3);
      align-items: flex-start;
    }
    h3 {
      margin: 0;
    }
    .heading > span {
      color: var(--vj-color-brand-strong);
      font-size: 0.78rem;
      font-weight: 700;
    }
    dl {
      display: grid;
      gap: var(--vj-space-2);
      margin: var(--vj-space-3) 0 0;
    }
    dl div {
      display: flex;
      flex-wrap: wrap;
      gap: var(--vj-space-2);
    }
    dt {
      color: var(--vj-color-muted);
      font-weight: 700;
    }
    dd {
      margin: 0;
      overflow-wrap: anywhere;
    }
    details {
      margin-top: var(--vj-space-3);
    }
    summary {
      cursor: pointer;
      color: var(--vj-color-brand-strong);
    }
  `,
})
export class EvidenceCardComponent {
  readonly title = input.required<string>();
  readonly classification = input.required<string>();
  readonly summary = input.required<string>();
  readonly source = input('');
  readonly observedAt = input('');
  readonly details = input<EvidenceDetail[]>([]);
}
