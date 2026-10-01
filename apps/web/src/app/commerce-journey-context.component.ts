import { ChangeDetectionStrategy, Component, Input, OnInit, inject, signal } from '@angular/core';
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
        <p class="journey-trust" role="note">{{ trustLabel(trust) }}</p>
      }
      <app-commerce-journey-stepper [stages]="value.stages" /><app-commerce-next-action
        [action]="value.next_action"
      />
      @if (value.commercial_readiness; as readiness) {
        <details class="journey-readiness" open>
          <summary>Commercial evidence readiness: {{ readiness.readiness.overall }}</summary>
          <p>Known {{ readiness.known_inputs.length }} · claimed {{ readiness.claims.length }} · assumed {{ readiness.assumptions.length }} · unknown {{ readiness.unknown_inputs.length }}</p>
          @if (readiness.missing_inputs.length) {
            <p><strong>Missing for calculation:</strong> {{ readiness.missing_inputs.length }} required input group(s).</p>
          }
          @if (readiness.readiness.safe_next_action; as action) {
            <p>{{ action }}</p>
          }
          <a href="/intelligence/sourcing-economics">Review commercial evidence</a>
        </details>
      }
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
      .journey-readiness {
        margin: 0.75rem 0;
        padding: 0.8rem;
        border: 1px solid #bfd8dc;
        border-radius: 0.5rem;
        background: #f2f9fa;
      }
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

  trustLabel(trust: { mode: string; label: string }): string {
    if (trust.label && trust.label !== 'UNKNOWN') return trust.label;
    if (trust.mode === 'LIVE_READ_ONLY') {
      return 'Live read-only research is configured. Review evidence before comparing products.';
    }
    if (trust.mode === 'LOCAL_FIXTURE' || trust.mode === 'LOCAL_DETERMINISTIC') {
      return 'Local demo data - not live market evidence.';
    }
    return 'Provider mode is not recorded for this goal yet. Check the Business Agent research status before continuing.';
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
