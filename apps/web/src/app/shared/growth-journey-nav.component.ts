import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

export type GrowthJourneyStep =
  | 'campaigns'
  | 'social'
  | 'advertising'
  | 'calendar'
  | 'approvals'
  | 'publishing'
  | 'recovery';

type JourneyLink = { key: GrowthJourneyStep; label: string; route: string };

@Component({
  selector: 'app-growth-journey-nav',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav class="growth-journey" aria-label="Growth journey">
      <ol>
        @for (step of steps; track step.key) {
          <li>
            <a
              [routerLink]="step.route"
              [attr.aria-current]="current() === step.key ? 'step' : null"
              [class.current]="current() === step.key"
              >{{ step.label }}</a
            >
          </li>
        }
      </ol>
      <p>Review, approval, scheduling, and recovery remain governed by the existing runtime.</p>
    </nav>
  `,
  styles: `
    :host {
      display: block;
      margin: 0 auto var(--vj-space-5);
      max-width: var(--vj-content-width);
    }
    ol {
      display: flex;
      flex-wrap: wrap;
      gap: var(--vj-space-2);
      margin: 0;
      padding: 0;
      list-style: none;
    }
    a {
      display: inline-flex;
      min-height: 2.35rem;
      align-items: center;
      padding: 0.45rem 0.75rem;
      border: 1px solid var(--vj-color-border-strong);
      border-radius: 999px;
      color: var(--vj-color-brand-strong);
      text-decoration: none;
      white-space: nowrap;
    }
    a:hover,
    a:focus-visible,
    a.current {
      border-color: var(--vj-color-brand);
      background: var(--vj-color-brand-soft);
      text-decoration: underline;
    }
    a.current {
      font-weight: 700;
    }
    p {
      margin: var(--vj-space-2) 0 0;
      color: var(--vj-color-muted);
      font-size: 0.86rem;
    }
    @media (max-width: 640px) {
      ol {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      a {
        justify-content: center;
        white-space: normal;
        text-align: center;
      }
    }
  `,
})
export class GrowthJourneyNavComponent {
  readonly current = input.required<GrowthJourneyStep>();
  readonly steps: JourneyLink[] = [
    { key: 'campaigns', label: 'Campaigns', route: '/campaigns' },
    { key: 'social', label: 'Social', route: '/social' },
    { key: 'advertising', label: 'Advertising', route: '/ads' },
    { key: 'calendar', label: 'Calendar', route: '/calendar' },
    { key: 'approvals', label: 'Approvals', route: '/approvals' },
    { key: 'publishing', label: 'Publishing', route: '/publishing' },
    { key: 'recovery', label: 'Recovery', route: '/operations/recovery' },
  ];
}
