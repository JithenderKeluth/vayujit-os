import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

export type SupplierJourneyStep =
  | 'discover'
  | 'compare'
  | 'shortlist'
  | 'verify'
  | 'scenarios'
  | 'resilience';

type JourneyLink = {
  key: SupplierJourneyStep;
  label: string;
  url: string;
};

@Component({
  selector: 'app-supplier-journey-nav',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav class="supplier-journey" aria-label="Supplier sourcing journey">
      <p class="eyebrow">Supplier journey</p>
      <ol>
        @for (step of steps; track step.key) {
          <li [class.current]="step.key === current()">
            @if (step.key === current()) {
              <span aria-current="step">{{ step.label }}</span>
            } @else {
              <a [routerLink]="step.url">{{ step.label }}</a>
            }
          </li>
        }
      </ol>
      <p class="journey-note">
        Evidence and trade-offs support a human sourcing decision; no supplier is selected or
        contacted automatically.
      </p>
    </nav>
  `,
  styles: `
    :host {
      display: block;
      margin: 0 auto var(--vj-space-5);
      max-width: var(--vj-content-width);
    }
    .supplier-journey {
      padding: var(--vj-space-4);
      border: 1px solid var(--vj-color-border);
      border-radius: var(--vj-radius-md);
      background: var(--vj-color-surface-muted);
    }
    .eyebrow {
      margin: 0 0 var(--vj-space-2);
      color: var(--vj-color-muted);
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    ol {
      display: flex;
      flex-wrap: wrap;
      gap: var(--vj-space-2);
      margin: 0;
      padding: 0;
      list-style: none;
    }
    li {
      display: inline-flex;
      align-items: center;
      min-height: 2.3rem;
      padding: 0.35rem 0.7rem;
      border: 1px solid var(--vj-color-border-strong);
      border-radius: 999px;
      background: var(--vj-color-surface);
    }
    li + li::before {
      content: '→';
      margin-right: var(--vj-space-2);
      color: var(--vj-color-muted);
    }
    li.current {
      border-color: var(--vj-color-brand);
      background: #e9f3f8;
      font-weight: 700;
    }
    a {
      color: var(--vj-color-brand-strong);
      text-decoration: none;
    }
    a:hover,
    a:focus-visible {
      text-decoration: underline;
    }
    .journey-note {
      margin: var(--vj-space-3) 0 0;
      color: var(--vj-color-ink-soft);
      font-size: 0.9rem;
    }
    @media (max-width: 640px) {
      li + li::before {
        content: '';
        margin: 0;
      }
    }
  `,
})
export class SupplierJourneyNavComponent {
  readonly current = input.required<SupplierJourneyStep>();
  readonly steps: JourneyLink[] = [
    { key: 'discover', label: 'Find suppliers', url: '/intelligence/cross-marketplace' },
    { key: 'compare', label: 'Compare', url: '/intelligence/cross-marketplace#comparison' },
    { key: 'shortlist', label: 'Shortlist', url: '/intelligence/supplier-shortlisting' },
    { key: 'verify', label: 'Verify', url: '/intelligence/due-diligence' },
    { key: 'scenarios', label: 'Sourcing scenarios', url: '/intelligence/sourcing-scenarios' },
    { key: 'resilience', label: 'Resilience', url: '/intelligence/supplier-portfolios' },
  ];
}
