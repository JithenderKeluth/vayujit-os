import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { CommerceJourneyService } from './commerce-journey.service';
import { CommerceJourneyStepperComponent } from './commerce-journey-stepper.component';
import { CommerceJourneySummaryComponent } from './commerce-journey-summary.component';
import { CommerceNextActionComponent } from './commerce-next-action.component';
import type { CommerceJourney } from './commerce-journey.types';

@Component({
  selector: 'app-commerce-journey-context',
  standalone: true,
  imports: [
    CommerceJourneyStepperComponent,
    CommerceJourneySummaryComponent,
    CommerceNextActionComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section class="commerce-journey-context" aria-label="Guided commerce context">
    @if (journey(); as value) {
      <app-commerce-journey-summary [journey]="value" />
    } @else if (showEmptyState) {
      <app-commerce-journey-summary [journey]="null" />
    }
    @if (journey(); as value) {
      @if (value.trust; as trust) {
        <p class="journey-trust" role="note">{{ trust.label }}</p>
      }
      <app-commerce-journey-stepper [stages]="value.stages" /><app-commerce-next-action
        [action]="value.next_action"
      />
      @if (value.context_confirmation.required) {
        <p class="journey-context-note">
          Confirm the proposed goal context in Business Agent before relying on it for consequential
          decisions.
        </p>
        <button
          type="button"
          class="op-button"
          (click)="confirmContext()"
          [disabled]="confirming()"
        >
          {{ confirming() ? 'Confirming…' : 'Confirm goal context' }}
        </button>
        @if (confirmationMessage()) {
          <p role="status">{{ confirmationMessage() }}</p>
        }
      }
    }
  </section>`,
  styles: [
    `
      .journey-trust {
        margin: 0.5rem 0;
        padding: 0.65rem 0.8rem;
        border-left: 3px solid #d49300;
        background: #fff8df;
      }
    `,
  ],
})
export class CommerceJourneyContextComponent implements OnInit {
  @Input() showEmptyState = true;
  private readonly service = inject(CommerceJourneyService, { optional: true });
  readonly journey = signal<CommerceJourney | null>(null);
  readonly confirming = signal(false);
  readonly confirmationMessage = signal('');

  ngOnInit(): void {
    if (this.service) void this.load();
  }

  private async load(): Promise<void> {
    try {
      this.journey.set(await this.service!.active());
    } catch {
      this.journey.set(null);
    }
  }

  async confirmContext(): Promise<void> {
    const current = this.journey();
    if (!this.service || !current) return;
    this.confirming.set(true);
    this.confirmationMessage.set('');
    try {
      this.journey.set(await this.service.confirmContext(current.id, current.context.values));
      this.confirmationMessage.set('Goal context confirmed.');
    } catch {
      this.confirmationMessage.set(
        'Context could not be confirmed. Review the goal in Business Agent.',
      );
    } finally {
      this.confirming.set(false);
    }
  }
}
import { Input } from '@angular/core';
