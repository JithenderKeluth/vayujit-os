import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { CommerceJourneyStage } from './commerce-journey.types';

@Component({
  selector: 'app-commerce-journey-stepper',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<nav class="commerce-journey-stepper" aria-label="Guided commerce journey">
    @for (stage of stages; track stage.key) {
      <a
        [routerLink]="stage.route"
        [attr.data-status]="stage.status"
        [class.current]="stage.status === 'IN_PROGRESS'"
        [class.ready]="stage.status === 'READY'"
        [class.blocked]="stage.status === 'BLOCKED'"
        [class.review]="stage.status === 'NEEDS_REVIEW'"
        [attr.aria-current]="stage.status === 'IN_PROGRESS' ? 'step' : null"
      >
        <span>{{ $index + 1 }}</span
        ><strong>{{ stage.label }}</strong
        ><small>{{ statusLabel(stage.status) }}</small>
      </a>
    }
  </nav>`,
  styles: [
    `
      .commerce-journey-stepper {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
        gap: 0.5rem;
        margin: 1rem 0;
      }
      .commerce-journey-stepper a {
        display: block;
        min-height: 4.5rem;
        border: 1px solid #bfd2d7;
        border-radius: var(--vj-radius-md);
        padding: var(--vj-space-3);
        text-decoration: none;
        color: inherit;
        background: var(--vj-color-surface);
        box-shadow: var(--vj-shadow-sm);
      }
      .commerce-journey-stepper a.current {
        border-color: var(--vj-color-brand);
        box-shadow: 0 0 0 2px var(--vj-color-brand-soft);
      }
      .commerce-journey-stepper a.ready {
        border-color: var(--vj-color-border-strong);
        background: var(--vj-color-brand-soft);
      }
      .commerce-journey-stepper a.blocked {
        opacity: 0.72;
      }
      .commerce-journey-stepper a.review {
        border-color: var(--vj-color-warning);
        background: var(--vj-color-warning-soft);
      }
      .commerce-journey-stepper span,
      .commerce-journey-stepper strong,
      .commerce-journey-stepper small {
        display: block;
      }
      .commerce-journey-stepper small {
        color: var(--vj-color-ink-soft);
        font-size: var(--vj-text-xs);
        margin-top: var(--vj-space-1);
      }
      @media (max-width: 560px) {
        .commerce-journey-stepper {
          grid-template-columns: 1fr 1fr;
        }
      }
    `,
  ],
})
export class CommerceJourneyStepperComponent {
  @Input({ required: true }) stages: CommerceJourneyStage[] = [];

  statusLabel(status: CommerceJourneyStage['status']): string {
    const labels: Record<CommerceJourneyStage['status'], string> = {
      COMPLETED: 'Completed',
      IN_PROGRESS: 'In progress',
      READY: 'Ready next',
      NEEDS_REVIEW: 'Needs review',
      BLOCKED: 'Blocked',
      NOT_STARTED: 'Not started',
    };
    return labels[status];
  }
}
