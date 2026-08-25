import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { IntelligenceService } from './intelligence.service';

@Component({
  selector: 'app-sourcing-workspace',
  imports: [FormsModule, RouterLink, JsonPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="sourcing-page" aria-labelledby="sourcing-title">
      <header class="page-header">
        <div>
          <p class="eyebrow">Intelligence / Sourcing</p>
          <h1 id="sourcing-title">Sourcing, RFQs &amp; landed-cost economics</h1>
          <p class="lede">
            Local deterministic workflow. Supplier contact, purchasing and payments remain disabled.
          </p>
        </div>
        <a routerLink="/intelligence">Back to Intelligence</a>
      </header>
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      <section class="metric-grid" aria-label="Sourcing overview">
        <article>
          <span>Active requirements</span
          ><strong>{{ overview()?.['active_requirements'] ?? 0 }}</strong>
        </article>
        <article>
          <span>Open RFQs</span><strong>{{ overview()?.['open_rfqs'] ?? 0 }}</strong>
        </article>
        <article>
          <span>Awaiting quotes</span><strong>{{ overview()?.['awaiting_quotes'] ?? 0 }}</strong>
        </article>
        <article>
          <span>Samples</span><strong>{{ overview()?.['samples'] ?? 0 }}</strong>
        </article>
        <article>
          <span>Inspections</span><strong>{{ overview()?.['inspections'] ?? 0 }}</strong>
        </article>
        <article>
          <span>Decisions awaiting review</span
          ><strong>{{ overview()?.['decisions_awaiting_review'] ?? 0 }}</strong>
        </article>
      </section>
      <nav class="tabs" aria-label="Sourcing sections">
        <a href="#requirements">Requirements</a>
        <a href="#rfqs">RFQs</a>
        <a href="#quotes">Quotes</a>
        <a href="#samples">Samples &amp; inspection</a>
        <a href="#comparison">Comparison</a>
        <a href="#negotiation">Negotiation</a>
        <a href="#economics">Landed cost &amp; economics</a>
        <a href="#sensitivity">Sensitivity</a>
        <a href="#capital">Capital &amp; cash</a>
        <a href="#critic">Critic</a>
        <a href="#concentration">Concentration</a>
        <a href="#decisions">Decisions</a>
      </nav>
      <section id="requirements" class="panel">
        <h2>Sourcing requirement</h2>
        <p>Pin product/opportunity context and preserve immutable requirement versions.</p>
        <form (submit)="$event.preventDefault(); createRequirement()" class="form-grid">
          <label
            >Product ID
            <input
              name="product"
              [(ngModel)]="requirement.product_id"
              placeholder="Optional product UUID"
          /></label>
          <label
            >Opportunity ID
            <input
              name="opportunity"
              [(ngModel)]="requirement.opportunity_id"
              placeholder="Optional opportunity UUID"
          /></label>
          <label
            >Category <input name="category" required [(ngModel)]="requirement.payload.category"
          /></label>
          <label
            >Target quantity
            <input
              name="quantity"
              type="number"
              min="1"
              [(ngModel)]="requirement.payload.target_quantity"
          /></label>
          <label
            >Target market <input name="market" [(ngModel)]="requirement.payload.target_market"
          /></label>
          <label
            >Max MOQ
            <input name="moq" type="number" min="1" [(ngModel)]="requirement.payload.maximum_moq"
          /></label>
          <button type="submit" [disabled]="busy()">Create requirement</button>
        </form>
        <ul>
          @for (row of requirements(); track row['id']) {
            <li>{{ row['id'] }} • v{{ row['current_version'] }} • {{ row['status'] }}</li>
          }
        </ul>
      </section>
      <section id="rfqs" class="panel">
        <h2>RFQ draft and approval boundary</h2>
        <p>Draft, review and approve locally; dispatch only records a manual state.</p>
        <form (submit)="$event.preventDefault(); createRFQ()" class="form-grid">
          <label
            >Requirement ID
            <input name="rfq-requirement" required [(ngModel)]="rfq.requirement_id" /></label
          ><label
            >Supplier IDs
            <input
              name="rfq-suppliers"
              required
              [(ngModel)]="rfq.supplier_ids_text"
              placeholder="UUID, UUID" /></label
          ><label>Title <input name="rfq-title" required [(ngModel)]="rfq.title" /></label
          ><button type="submit" [disabled]="busy()">Create RFQ</button>
        </form>
      </section>
      <section id="quotes" class="panel">
        <h2>Manual supplier quotes</h2>
        <p>Quote versions append; currencies are never silently converted.</p>
        <form (submit)="$event.preventDefault(); createQuote()" class="form-grid">
          <label>RFQ ID <input name="quote-rfq" required [(ngModel)]="quote.rfq_id" /></label
          ><label
            >Supplier ID
            <input name="quote-supplier" required [(ngModel)]="quote.supplier_id" /></label
          ><label
            >Reference
            <input name="quote-reference" required [(ngModel)]="quote.quote_reference" /></label
          ><label
            >Currency
            <input
              name="quote-currency"
              required
              maxlength="3"
              [(ngModel)]="quote.currency" /></label
          ><label
            >Unit price
            <input
              name="quote-price"
              required
              type="number"
              min="0"
              [(ngModel)]="quote.unit_price" /></label
          ><label
            >MOQ
            <input name="quote-moq" required type="number" min="1" [(ngModel)]="quote.moq" /></label
          ><button type="submit" [disabled]="busy()">Capture quote version</button>
        </form>
        <button type="button" (click)="loadQuotes()">Refresh quotes</button>
        <ul>
          @for (row of quotes(); track row['id']) {
            <li>
              {{ row['quote_reference'] }} • v{{ row['version'] }} • {{ row['currency'] }}
              {{ row['unit_price'] }}
            </li>
          }
        </ul>
      </section>
      <section id="samples" class="panel">
        <h2>Samples &amp; inspections</h2>
        <p>Evidence references and structured evaluation stay local and reviewable.</p>
        <form (submit)="$event.preventDefault(); createSample()" class="form-grid">
          <label
            >Supplier ID
            <input name="sample-supplier" required [(ngModel)]="sample.supplier_id" /></label
          ><label>RFQ ID <input name="sample-rfq" [(ngModel)]="sample.rfq_id" /></label
          ><label
            >Quantity
            <input
              name="sample-quantity"
              type="number"
              min="1"
              [(ngModel)]="sample.quantity" /></label
          ><button type="submit" [disabled]="busy()">Request sample</button>
        </form>
      </section>
      <section id="economics" class="panel">
        <h2>Landed cost &amp; economics</h2>
        <p>
          Values are observed, configured, assumed or unknown; no live freight, FX or customs data
          is used.
        </p>
        <form (submit)="$event.preventDefault(); calculate()" class="form-grid">
          <label
            >Requirement ID
            <input name="cost-requirement" [(ngModel)]="scenario.requirement_id" /></label
          ><label
            >Supplier price
            <input
              name="cost-price"
              type="number"
              min="0"
              [(ngModel)]="scenario.inputs.unit_supplier_price" /></label
          ><label
            >Freight assumption
            <input
              name="cost-freight"
              type="number"
              min="0"
              [(ngModel)]="scenario.inputs.freight" /></label
          ><label
            >Selling price
            <input
              name="cost-selling"
              type="number"
              min="0"
              [(ngModel)]="scenario.inputs.selling_price" /></label
          ><label
            >Quantity
            <input
              name="cost-quantity"
              type="number"
              min="1"
              [(ngModel)]="scenario.inputs.quantity" /></label
          ><button type="submit" [disabled]="busy()">Calculate deterministic scenario</button>
        </form>
        @if (lastScenario()) {
          <pre aria-label="Cost result">{{ lastScenario() | json }}</pre>
        }
      </section>
      <section id="comparison" class="panel evidence-panel">
        <h2>Quote comparison</h2>
        <p>
          Compare supplier versions by currency, MOQ, evidence freshness and landed-cost
          assumptions.
        </p>
      </section>
      <section id="negotiation" class="panel evidence-panel">
        <h2>Negotiation history</h2>
        <p>Negotiation rounds are append-only review records; no supplier message is sent.</p>
      </section>
      <section id="sensitivity" class="panel evidence-panel">
        <h2>Sensitivity analysis</h2>
        <p>
          Review supplier price, freight, FX, selling price, advertising CAC, returns and MOQ
          scenarios.
        </p>
      </section>
      <section id="capital" class="panel evidence-panel">
        <h2>Capital and cash timeline</h2>
        <p>
          See sample, tooling, deposit, balance, freight, duty, tax and receivable timing
          assumptions.
        </p>
      </section>
      <section id="critic" class="panel evidence-panel">
        <h2>Critic findings</h2>
        <p>
          Surface missing evidence, stale assumptions, margin risk and review blockers before a
          decision.
        </p>
      </section>
      <section id="concentration" class="panel evidence-panel">
        <h2>Supplier concentration</h2>
        <p>
          Classifications include SINGLE_SOURCE, DUAL_SOURCE, MULTI_SOURCE and
          INSUFFICIENT_EVIDENCE.
        </p>
      </section>
      <section id="decisions" class="panel">
        <h2>Human sourcing decision</h2>
        <p>Approval ends this slice. It never creates a purchase order, receipt or payment.</p>
        <form (submit)="$event.preventDefault(); createDecision()" class="form-grid">
          <label
            >Requirement ID
            <input
              name="decision-requirement"
              required
              [(ngModel)]="decision.requirement_id" /></label
          ><label
            >Quote ID
            <input name="decision-quote" required [(ngModel)]="decision.quote_id" /></label
          ><label
            >Decision
            <select name="decision" [(ngModel)]="decision.decision">
              <option>hold</option>
              <option>request_negotiation</option>
              <option>request_requote</option>
              <option>approve_for_future_purchase</option>
              <option>reject</option>
            </select></label
          ><label class="check"
            ><input type="checkbox" name="confirm" [(ngModel)]="decision.confirmed" /> Confirm for
            human review</label
          ><button type="submit" [disabled]="busy()">Record decision</button>
        </form>
      </section>
    </main>
  `,
  styles: [
    `
      :host {
        display: block;
        color: #082331;
      }
      .sourcing-page {
        padding: 2rem;
        max-width: 1400px;
        margin: auto;
      }
      .page-header {
        display: flex;
        justify-content: space-between;
        gap: 2rem;
        align-items: flex-start;
      }
      h1 {
        font-size: clamp(2rem, 4vw, 3.2rem);
        margin: 0.25rem 0;
      }
      .lede {
        color: #537084;
      }
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 1rem;
        margin: 2rem 0;
      }
      .metric-grid article {
        border: 1px solid #c7d9df;
        border-radius: 14px;
        padding: 1rem;
        background: #fff;
        min-height: 78px;
      }
      .metric-grid span {
        display: block;
        color: #537084;
      }
      strong {
        font-size: 1.8rem;
      }
      .tabs {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
        margin: 1rem 0 2rem;
      }
      .tabs a {
        border: 1px solid #8db3c2;
        border-radius: 999px;
        padding: 0.55rem 0.8rem;
        text-decoration: none;
      }
      .panel {
        border: 1px solid #c7d9df;
        border-radius: 14px;
        padding: 1.25rem;
        margin: 1rem 0;
        background: #fff;
      }
      .panel h2 {
        margin-top: 0;
      }
      .form-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: 1rem;
        align-items: end;
      }
      label {
        display: grid;
        gap: 0.35rem;
      }
      input,
      select,
      button {
        font: inherit;
        padding: 0.65rem;
        border-radius: 8px;
        border: 1px solid #9dbac5;
      }
      button {
        background: #165d75;
        color: #fff;
        cursor: pointer;
      }
      button:disabled {
        opacity: 0.55;
      }
      .check {
        display: flex;
        align-items: center;
      }
      .error {
        background: #fff0f0;
        color: #a51f2a;
        padding: 1rem;
      }
      pre {
        overflow: auto;
        background: #f4f8f9;
        padding: 1rem;
      }
      @media (max-width: 600px) {
        .sourcing-page {
          padding: 1rem;
        }
        .page-header {
          flex-direction: column;
        }
      }
    `,
  ],
})
export class SourcingWorkspaceComponent {
  private readonly service = inject(IntelligenceService);
  readonly overview = signal<Record<string, unknown> | null>(null);
  readonly requirements = signal<Record<string, unknown>[]>([]);
  readonly quotes = signal<Record<string, unknown>[]>([]);
  readonly lastScenario = signal<Record<string, unknown> | null>(null);
  readonly error = signal('');
  readonly busy = signal(false);
  readonly requirement = {
    product_id: '',
    opportunity_id: '',
    payload: { category: '', target_quantity: 1, target_market: '', maximum_moq: 100 },
  };
  readonly rfq = { requirement_id: '', supplier_ids_text: '', title: 'Local sourcing request' };
  readonly quote = {
    rfq_id: '',
    supplier_id: '',
    quote_reference: '',
    currency: 'INR',
    unit_price: 0,
    moq: 1,
  };
  readonly sample = { rfq_id: '', supplier_id: '', quantity: 1 };
  readonly scenario = {
    requirement_id: '',
    inputs: { unit_supplier_price: 0, freight: 0, selling_price: 0, quantity: 1 },
  };
  readonly decision = { requirement_id: '', quote_id: '', decision: 'hold', confirmed: false };
  constructor() {
    void this.load();
  }
  private async load(): Promise<void> {
    try {
      this.overview.set(await this.service.sourcingOverview());
      this.requirements.set(
        ((await this.service.sourcingRequirements())['items'] as Record<string, unknown>[]) ?? [],
      );
    } catch {
      this.error.set('Sourcing data is unavailable. Check the authenticated API connection.');
    }
  }
  async createRequirement(): Promise<void> {
    await this.run(async () => {
      await this.service.createSourcingRequirement({
        ...this.requirement,
        idempotency_key: 'requirement-' + crypto.randomUUID(),
      });
      await this.load();
    });
  }
  async createRFQ(): Promise<void> {
    await this.run(async () => {
      await this.service.createRFQ({
        requirement_id: this.rfq.requirement_id,
        requirement_version: 1,
        title: this.rfq.title,
        supplier_ids: this.rfq.supplier_ids_text
          .split(',')
          .map((v) => v.trim())
          .filter(Boolean),
        idempotency_key: 'rfq-' + crypto.randomUUID(),
        payload: {},
      });
    });
  }
  async createQuote(): Promise<void> {
    await this.run(async () => {
      await this.service.createSourcingQuote({
        ...this.quote,
        lines: [],
        payload: {},
        evidence_refs: [],
      });
      await this.loadQuotes();
    });
  }
  async loadQuotes(): Promise<void> {
    await this.run(async () => {
      this.quotes.set(
        ((await this.service.sourcingQuotes())['items'] as Record<string, unknown>[]) ?? [],
      );
    });
  }
  async createSample(): Promise<void> {
    await this.run(async () => {
      await this.service.createSampleRequest(this.sample);
    });
  }
  async calculate(): Promise<void> {
    await this.run(async () => {
      this.lastScenario.set(
        await this.service.createCostScenario({ name: 'BASE', currency: 'INR', ...this.scenario }),
      );
    });
  }
  async createDecision(): Promise<void> {
    await this.run(async () => {
      await this.service.createSourcingDecision({
        ...this.decision,
        classification: 'review_required',
        critic: [],
      });
    });
  }
  private async run(work: () => Promise<void>): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      await work();
    } catch {
      this.error.set('The sourcing operation could not be completed safely.');
    } finally {
      this.busy.set(false);
    }
  }
}
