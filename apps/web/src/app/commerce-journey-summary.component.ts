import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { CommerceJourney } from './commerce-journey.types';

@Component({
  selector: 'app-commerce-journey-summary',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section
    class="commerce-journey-summary"
    aria-labelledby="commerce-journey-summary-title"
  >
    <div>
      <p class="eyebrow">Guided commerce journey</p>
      <h2 id="commerce-journey-summary-title">
        {{ journey ? 'Continue your journey' : 'Start a guided journey' }}
      </h2>
      @if (journey) {
        <p>
          {{ journey.completed_stage_count }} of {{ journey.total_stage_count }} stages complete.
          Next: {{ journey.next_action.detail }}
        </p>
        @if (contextFacts(journey).length) {
          <div role="group" aria-label="Active goal context">
            <dl class="journey-context-facts">
              @for (fact of contextFacts(journey); track fact.label) {
                <div>
                  <dt>{{ fact.label }}</dt>
                  <dd>{{ fact.value }}</dd>
                </div>
              }
            </dl>
          </div>
        }
      } @else {
        <p>
          Start with a Business Agent goal to keep research, supplier checks, economics, and launch
          decisions connected.
        </p>
      }
    </div>
    @if (journey) {
      <a class="op-button primary" [routerLink]="journey.next_action.route">{{
        journey.next_action.title
      }}</a>
    } @else {
      <a class="op-button primary" routerLink="/intelligence/business-agent">Open Business Agent</a>
    }
  </section>`,
  styles: [
    `
      .commerce-journey-summary {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
        border: 1px solid #bfd2d7;
        border-radius: 0.7rem;
        padding: 1rem;
        margin: 1rem 0;
        background: #f7fbfb;
      }
      .commerce-journey-summary > div {
        min-width: 0;
      }
      .commerce-journey-summary p {
        max-width: 70ch;
      }
      .journey-context-facts {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem 1rem;
        margin: 0.75rem 0 0;
      }
      .journey-context-facts > div {
        display: grid;
        gap: 0.1rem;
        min-width: 8rem;
      }
      .journey-context-facts dt {
        color: #5c7883;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }
      .journey-context-facts dd {
        margin: 0;
        overflow-wrap: anywhere;
      }
      @media (max-width: 680px) {
        .commerce-journey-summary {
          align-items: stretch;
          flex-direction: column;
        }
        .commerce-journey-summary .op-button {
          width: 100%;
          text-align: center;
        }
      }
    `,
  ],
})
export class CommerceJourneySummaryComponent {
  @Input() journey: CommerceJourney | null = null;

  contextFacts(journey: CommerceJourney): Array<{ label: string; value: string }> {
    const values = journey.context.values;
    const facts: Array<{ label: string; value: string }> = [];
    const add = (label: string, value: unknown): void => {
      if (typeof value === 'string' && value.trim()) facts.push({ label, value: value.trim() });
      else if (typeof value === 'number' && Number.isFinite(value))
        facts.push({ label, value: String(value) });
    };
    add('Category', values['category']);
    add('Marketplace', values['marketplace']);
    add('Budget', values['budget'] ?? values['capital'] ?? values['initial_budget']);
    add('Currency', values['currency']);
    return facts;
  }
}
