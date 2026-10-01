import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { PageHeaderComponent } from '../shared/page-header.component';
import { CommerceJourneyContextComponent } from '../commerce-journey-context.component';
import {
  BlockedStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';
import { IntelligenceService } from './intelligence.service';
import { SupplierJourneyNavComponent } from './supplier-journey-nav.component';

@Component({
  selector: 'app-sourcing-workspace',
  imports: [
    BlockedStateComponent,
    PageHeaderComponent,
    BreadcrumbsComponent,
    CommerceJourneyContextComponent,
    ErrorStateComponent,
    FormsModule,
    JsonPipe,
    LoadingStateComponent,
    RouterLink,
    SupplierJourneyNavComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <main class="sourcing-page" aria-labelledby="sourcing-title">
      <app-breadcrumbs [items]="breadcrumbs" />

      <app-page-header
        headingId="sourcing-title"
        eyebrow="Intelligence / Sourcing workspace"
        title="Make a sourcing decision"
        description="Move from a selected product and shortlisted suppliers to evidence-backed commercial review. Supplier contact, purchasing, and payments remain disabled."
      >
        <a page-header-actions routerLink="/intelligence">Back to Intelligence</a>
      </app-page-header>
      <app-supplier-journey-nav current="scenarios" />
      <app-commerce-journey-context />
      @if (selectedContext(); as context) {
        <section class="context-banner" aria-label="Selected product context">
          <strong>Selected product:</strong> {{ context.name || context.product }} ·
          {{ context.category || 'Category not recorded'
          }}<span
            >Context carried from Product Research; confirm before creating a sourcing
            requirement.</span
          >
        </section>
      }
      @if (selectedContext(); as context) {
        <section class="context-summary" aria-label="Sourcing context facts">
          <span class="status-pill">PRODUCT CONTEXT</span>
          <strong>{{ context.name || context.product || 'Selected product' }}</strong>
          <div class="context-facts">
            <span>{{ context.category || 'Category unknown' }}</span>
            <span>{{ context.marketplace || 'Marketplace unknown' }}</span>
            <span>{{ context.market || 'Market unknown' }}</span>
            <span>{{ context.currency || 'Currency unknown' }}</span>
            <span>{{ supplierOptions().length }} shortlisted supplier(s)</span>
            <span>{{ context.verification }}</span>
          </div>
          <small
            >No UUID re-entry is needed; context is carried from Product Research and Supplier
            Intelligence.</small
          >
        </section>
      } @else {
        <section class="blocked-banner" aria-label="Sourcing prerequisite">
          <app-blocked-state
            title="Select a product before starting sourcing"
            reason="Open Product Opportunities and choose the product to evaluate before creating a sourcing requirement."
          />
          <a routerLink="/intelligence/product-opportunities">Open Product Opportunities</a>
        </section>
      }
      @if (error()) {
        <app-error-state title="Sourcing data is unavailable" [message]="error()" />
      }
      @if (busy()) {
        <app-loading-state message="Updating sourcing workspace..." />
      }
      <section class="readiness panel" aria-labelledby="readiness-title">
        <div>
          <p class="eyebrow">SOURCING OVERVIEW</p>
          <h2 id="readiness-title">Know what is ready before you spend</h2>
          <p>
            Each stage stays explicit about evidence, assumptions, missing inputs, and human
            approval.
          </p>
        </div>
        <div class="readiness-grid">
          <article>
            <span>Requirement</span
            ><strong>{{ requirements().length ? 'READY' : 'NEEDS SETUP' }}</strong
            ><small>{{
              requirements().length
                ? 'Current requirement available'
                : 'Confirm product and quantity'
            }}</small>
          </article>
          <article>
            <span>Suppliers</span
            ><strong>{{ supplierOptions().length ? 'SHORTLISTED' : 'NEEDS REVIEW' }}</strong
            ><small>{{ supplierOptions().length }} supplier(s) carried from research</small>
          </article>
          <article>
            <span>Quotes</span><strong>{{ quotes().length ? 'RECORDED' : 'NOT RECORDED' }}</strong
            ><small>{{
              quotes().length ? 'Review provenance before use' : 'No supplier pricing yet'
            }}</small>
          </article>
          <article>
            <span>Economics</span><strong>{{ lastScenario() ? 'MODELED' : 'NOT READY' }}</strong
            ><small>{{
              lastScenario()
                ? 'Known inputs only'
                : 'Requires quote, freight, and selling-price inputs'
            }}</small>
          </article>
        </div>
        <div class="next-action">
          <span class="status-pill">NEXT BEST ACTION</span
          ><strong>{{
            requirements().length
              ? quotes().length
                ? lastScenario()
                  ? 'Review the Decision Brief'
                  : 'Complete landed-cost inputs'
                : 'Collect or record a supplier quote'
              : 'Confirm the sourcing requirement'
          }}</strong
          ><span>{{
            requirements().length
              ? quotes().length
                ? lastScenario()
                  ? 'Compare scenarios and record an explicit human decision.'
                  : 'Unknown freight, FX, duty, and tax stay visible until evidenced.'
                : 'RFQ preparation is local; sending remains a human-controlled action.'
              : 'Start with quantity, market, and supplier constraints.'
          }}</span>
        </div>
      </section>
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
        <a href="#requirements" (click)="activateSection($event, 'requirements')">Requirements</a>
        <a href="#rfqs" (click)="activateSection($event, 'rfqs')">RFQs</a>
        <a href="#quotes" (click)="activateSection($event, 'quotes')">Quotes</a>
        <a href="#samples" (click)="activateSection($event, 'samples')">Samples &amp; inspection</a>
        <a href="#comparison" (click)="activateSection($event, 'comparison')">Comparison</a>
        <a href="#negotiation" (click)="activateSection($event, 'negotiation')">Negotiation</a>
        <a href="#economics" (click)="activateSection($event, 'economics')"
          >Landed cost &amp; economics</a
        >
        <a href="#sensitivity" (click)="activateSection($event, 'sensitivity')">Sensitivity</a>
        <a href="#capital" (click)="activateSection($event, 'capital')">Capital &amp; cash</a>
        <a href="#critic" (click)="activateSection($event, 'critic')">Critic</a>
        <a href="#concentration" (click)="activateSection($event, 'concentration')"
          >Concentration</a
        >
        <a href="#decisions" (click)="activateSection($event, 'decisions')">Decisions</a>
      </nav>
      <section id="requirements" class="panel">
        <h2>Confirm the sourcing requirement</h2>
        <p>
          Confirm the business constraints suppliers should price. Product context is carried from
          the selected opportunity.
        </p>
        <form (submit)="$event.preventDefault(); createRequirement()" class="form-grid">
          <label
            >Category <input name="category" required [(ngModel)]="requirement.payload.category"
          /></label>
          <label
            >Target quantity <small class="field-help">Required starting quantity</small>
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
            >Maximum MOQ <small class="field-help">Leave blank if unknown</small>
            <input name="moq" type="number" min="1" [(ngModel)]="requirement.payload.maximum_moq"
          /></label>
          <button type="submit" [disabled]="busy() || !selectedContext()">
            Confirm requirement
          </button>
        </form>
        <details class="advanced-panel">
          <summary>Advanced requirement identifiers</summary>
          <p class="hint">
            Technical identifiers are retained for audit; they are not needed for the normal
            journey.
          </p>
          <dl class="technical-list">
            <div>
              <dt>Product ID</dt>
              <dd>{{ requirement.product_id || 'AUTO-RESOLVED / UNKNOWN' }}</dd>
            </div>
            <div>
              <dt>Opportunity ID</dt>
              <dd>{{ requirement.opportunity_id || 'AUTO-RESOLVED / UNKNOWN' }}</dd>
            </div>
          </dl>
        </details>
        <ul>
          @for (row of requirements(); track row['id']) {
            <li>Requirement version {{ row['current_version'] }} - {{ row['status'] }}</li>
          }
        </ul>
      </section>
      <section id="rfqs" class="panel">
        <h2>Prepare a supplier pricing request</h2>
        <p>
          Prepare an RFQ for human review. Preparing it never sends a message or contacts a
          supplier.
        </p>
        @if (!requirements().length || !supplierOptions().length) {
          <app-blocked-state
            title="Prepare an RFQ after the requirement and shortlist are ready"
            [reason]="
              !requirements().length
                ? 'Confirm the sourcing requirement first.'
                : 'Shortlist suppliers before preparing an RFQ.'
            "
          />
          <a routerLink="/intelligence/cross-marketplace">Review Supplier Intelligence</a>
        } @else {
          <form (submit)="$event.preventDefault(); createRFQ()" class="form-grid">
            <label>RFQ title <input name="rfq-title" required [(ngModel)]="rfq.title" /></label>
            <fieldset class="supplier-picker">
              <legend>Suppliers to request pricing from</legend>
              @for (supplier of supplierOptions(); track supplier.id) {
                <label class="check"
                  ><input
                    type="checkbox"
                    [checked]="rfq.supplier_ids_text.includes(supplier.id)"
                    (change)="toggleSupplier(supplier.id)"
                  />
                  {{ supplier.name }}</label
                >
              }
            </fieldset>
            <button type="submit" [disabled]="busy() || !rfq.supplier_ids_text">
              Prepare RFQ for review
            </button>
          </form>
          <div class="boundary-note">
            <strong>Prepared locally</strong
            ><span
              >Dispatch, email, marketplace messaging, and supplier contact remain disabled.</span
            >
          </div>
        }
        <details class="advanced-panel">
          <summary>Advanced RFQ controls</summary>
          <label
            >Requirement ID
            <input
              name="rfq-requirement"
              [(ngModel)]="rfq.requirement_id"
              placeholder="Auto-resolved from current requirement"
          /></label>
          <label
            >Supplier IDs
            <input
              name="rfq-suppliers"
              [(ngModel)]="rfq.supplier_ids_text"
              placeholder="Auto-resolved from shortlist"
          /></label>
        </details>
      </section>
      <section id="quotes" class="panel">
        <h2>Record supplier quotes</h2>
        <p>
          Quotes are supplier-provided or manually entered evidence. Currency is shown as supplied;
          no silent conversion occurs.
        </p>
        <form (submit)="$event.preventDefault(); createQuote()" class="form-grid">
          <label
            >Supplier
            <select name="quote-supplier" [(ngModel)]="quote.supplier_id">
              <option value="">Select shortlisted supplier</option>
              @for (supplier of supplierOptions(); track supplier.id) {
                <option [value]="supplier.id">{{ supplier.name }}</option>
              }
            </select></label
          ><label
            >Quote reference
            <input
              name="quote-reference"
              required
              [(ngModel)]="quote.quote_reference"
              placeholder="Supplier reference or note" /></label
          ><label
            >Currency
            <input
              name="quote-currency"
              required
              maxlength="3"
              [(ngModel)]="quote.currency" /></label
          ><label
            >Quoted unit price
            <small class="field-help">Required; leave unknown values blank</small>
            <input
              name="quote-price"
              required
              type="number"
              min="0"
              [(ngModel)]="quote.unit_price" /></label
          ><label
            >MOQ
            <small class="field-help">Unknown until supplied by the seller</small>
            <input name="quote-moq" required type="number" min="1" [(ngModel)]="quote.moq" /></label
          ><button
            type="submit"
            [disabled]="busy() || !quote.supplier_id || !(quote.rfq_id || rfqId())"
          >
            Record supplier quote
          </button>
        </form>
        <button type="button" class="secondary-action" (click)="loadQuotes()">
          Refresh recorded quotes
        </button>
        <ul>
          @for (row of quotes(); track row['id']) {
            <li>
              {{ row['quote_reference'] }} • v{{ row['version'] }} • {{ row['currency'] }}
              {{ row['unit_price'] }}
            </li>
          }
        </ul>
        <details class="advanced-panel">
          <summary>Advanced quote identifiers and provenance</summary>
          <label
            >RFQ ID
            <input
              name="quote-rfq"
              [(ngModel)]="quote.rfq_id"
              placeholder="Auto-resolved from prepared RFQ"
          /></label>
          <p class="hint">
            Supplier quote, observed listing price, user assumption, and calculated values remain
            separate evidence types.
          </p>
        </details>
      </section>
      <section id="samples" class="panel">
        <h2>Validate samples and inspections</h2>
        <p>
          Use samples and inspections to reduce supplier risk before relying on commercial
          assumptions.
        </p>
        <form (submit)="$event.preventDefault(); createSample()" class="form-grid">
          <label
            >Supplier
            <select name="sample-supplier" [(ngModel)]="sample.supplier_id">
              <option value="">Select shortlisted supplier</option>
              @for (supplier of supplierOptions(); track supplier.id) {
                <option [value]="supplier.id">{{ supplier.name }}</option>
              }
            </select></label
          ><label
            >Quantity
            <input
              name="sample-quantity"
              type="number"
              min="1"
              [(ngModel)]="sample.quantity" /></label
          ><button type="submit" [disabled]="busy() || !sample.supplier_id">
            Request sample locally
          </button>
        </form>
        <div class="boundary-note">
          <strong>Evidence step only</strong
          ><span
            >Sample status, cost, outcome, and evidence remain reviewable; no order or payment is
            created.</span
          >
        </div>
        <details class="advanced-panel">
          <summary>Advanced sample/RFQ identifiers</summary>
          <label>RFQ ID <input name="sample-rfq" [(ngModel)]="sample.rfq_id" /></label>
        </details>
      </section>
      <section id="economics" class="panel">
        <h2>Complete landed-cost inputs</h2>
        <p>
          Use the authoritative Sourcing Economics workspace for immutable snapshots, FX, freight,
          duty/tax, sensitivity, capital, and Decision Brief output. Unknown values stay unknown.
        </p>
        <div class="economics-handoff">
          <strong>{{
            lastScenario() ? 'Known-cost scenario available' : 'Landed cost is not complete yet'
          }}</strong
          ><span>{{
            lastScenario()
              ? 'Review the result below, then open the full Decision Brief.'
              : 'Missing freight, FX, duty/tax, or selling-price evidence must stay visible.'
          }}</span
          ><a routerLink="/intelligence/sourcing-economics" [queryParams]="economicsQuery()"
            >Open landed-cost economics</a
          >
        </div>
        <details class="advanced-panel">
          <summary>Advanced local scenario tool</summary>
          <p class="hint">
            This preserves the existing deterministic behavior and never recalculates authoritative
            economics in Angular.
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
        </details>
      </section>
      <section id="comparison" class="panel evidence-panel">
        <h2>Quote comparison</h2>
        <p>
          Compare suppliers and scenarios on cost, MOQ, lead time, evidence completeness, risk, and
          important unknowns. The workspace never picks a winner automatically.
        </p>
        <div class="comparison-callout">
          <strong>{{
            quotes().length
              ? quotes().length + ' quote(s) available for review'
              : 'No comparable quote yet'
          }}</strong
          ><span>{{
            quotes().length
              ? 'Open Sourcing Economics to compare authoritative scenarios and sensitivity.'
              : 'Record supplier pricing before comparing options.'
          }}</span
          ><a routerLink="/intelligence/sourcing-economics">Compare scenarios</a>
        </div>
      </section>
      <section id="negotiation" class="panel evidence-panel">
        <h2>Negotiation history</h2>
        <p>Negotiation rounds are append-only review records; no supplier message is sent.</p>
      </section>
      <section id="sensitivity" class="panel evidence-panel">
        <h2>Sensitivity analysis</h2>
        <p>
          Review only the dimensions supported by the authoritative 13F/13G calculation. Unknown or
          stale inputs remain visible.
        </p>
        <a routerLink="/intelligence/sourcing-economics">Review sensitivity</a>
      </section>
      <section id="capital" class="panel evidence-panel">
        <h2>Capital and cash timeline</h2>
        <p>
          Capital means the costs included by the current model. Advertising, marketplace fees,
          returns, and working capital are excluded unless explicitly modeled.
        </p>
        <a routerLink="/intelligence/sourcing-economics">Review capital requirement</a>
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
          {{
            supplierOptions().length > 1
              ? 'Multiple shortlisted suppliers are available for comparison.'
              : supplierOptions().length === 1
                ? 'Current sourcing evidence depends on one shortlisted supplier.'
                : 'Supplier concentration cannot be assessed until suppliers are shortlisted.'
          }}
        </p>
      </section>
      <section id="decisions" class="panel">
        <h2>Human sourcing decision</h2>
        <p>
          Proceed means launch preparation only. It never creates a purchase order, receipt,
          payment, listing, or supplier message.
        </p>
        @if (!lastScenario()) {
          <app-blocked-state
            title="Complete enough economics to review a decision brief"
            reason="Review landed-cost inputs and evidence before recording a human sourcing decision."
          />
          <a routerLink="/intelligence/sourcing-economics">Open Decision Brief</a>
        }
        <form (submit)="$event.preventDefault(); createDecision()" class="form-grid">
          <label
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
          ><button type="submit" [disabled]="busy() || !decision.confirmed">
            Record human decision
          </button>
        </form>
        <details class="advanced-panel">
          <summary>Advanced decision identifiers</summary>
          <label
            >Requirement ID
            <input name="decision-requirement" [(ngModel)]="decision.requirement_id"
          /></label>
          <label>Quote ID <input name="decision-quote" [(ngModel)]="decision.quote_id" /></label>
        </details>
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
      .context-banner {
        display: none;
      }
      .context-summary,
      .blocked-banner,
      .next-action,
      .boundary-note,
      .economics-handoff,
      .comparison-callout,
      .empty-state,
      .success-note {
        display: grid;
        gap: 0.45rem;
        padding: 1rem;
        border-radius: 10px;
      }
      .context-summary {
        margin: 1rem 0;
        border: 1px solid #b7d6dc;
        background: #f3fbfb;
      }
      .context-title,
      .context-facts {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        align-items: center;
      }
      .context-facts span {
        padding: 0.3rem 0.55rem;
        border: 1px solid #c7d9df;
        border-radius: 999px;
        background: #fff;
      }
      .status-pill,
      .step-status {
        color: #075b6d;
        font-size: 0.75rem;
        font-weight: 800;
        letter-spacing: 0.08em;
      }
      .blocked-banner,
      .empty-state {
        border-left: 4px solid #d69e2e;
        background: #fff9e7;
      }
      .readiness {
        background: #f7fbfb;
      }
      .readiness-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.75rem;
        margin: 1rem 0;
      }
      .readiness-grid article {
        display: grid;
        gap: 0.35rem;
        padding: 0.9rem;
        border: 1px solid #c7d9df;
        border-radius: 10px;
        background: #fff;
      }
      .readiness-grid strong {
        font-size: 1rem;
      }
      .readiness-grid small,
      .field-help,
      .hint {
        color: #537084;
        font-size: 0.86rem;
      }
      .next-action,
      .economics-handoff,
      .comparison-callout,
      .boundary-note,
      .success-note {
        border-left: 4px solid #147d8c;
        background: #edf7f7;
      }
      .phase-tabs a {
        font-weight: 700;
      }
      .workflow-step {
        scroll-margin-top: 1rem;
      }
      .step-heading {
        display: flex;
        gap: 0.75rem;
        align-items: center;
      }
      .step-heading h2 {
        margin: 0.1rem 0;
      }
      .step-heading .eyebrow {
        margin: 0;
      }
      .step-number {
        display: grid;
        place-items: center;
        width: 2rem;
        height: 2rem;
        border-radius: 50%;
        background: #165d75;
        color: #fff;
        font-weight: 800;
      }
      .step-status {
        margin-left: auto;
      }
      .advanced-panel {
        margin-top: 1rem;
        padding-top: 0.75rem;
        border-top: 1px solid #d6e0e5;
      }
      .advanced-panel summary {
        cursor: pointer;
        font-weight: 700;
      }
      .supplier-picker {
        display: grid;
        gap: 0.5rem;
        border: 1px solid #9dbac5;
        border-radius: 8px;
        padding: 0.75rem;
      }
      .supplier-picker legend {
        padding: 0 0.35rem;
        font-weight: 700;
      }
      .quote-list {
        display: grid;
        gap: 0.5rem;
        margin-top: 0.75rem;
      }
      .quote-list li {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        padding: 0.75rem;
        border: 1px solid #d6e0e5;
        border-radius: 8px;
      }
      .secondary-action {
        margin-top: 0.75rem;
        background: #fff;
        color: #165d75;
      }
      .technical-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 0.75rem;
      }
      .technical-list div {
        padding: 0.75rem;
        border: 1px solid #d6e0e5;
        border-radius: 8px;
      }
      .technical-list dd {
        margin: 0.3rem 0 0;
        overflow-wrap: anywhere;
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
  private readonly route = inject(ActivatedRoute);
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Intelligence', url: '/intelligence' },
    { label: 'Sourcing workspace' },
  ];
  readonly overview = signal<Record<string, unknown> | null>(null);
  readonly requirements = signal<Record<string, unknown>[]>([]);
  readonly quotes = signal<Record<string, unknown>[]>([]);
  readonly lastScenario = signal<Record<string, unknown> | null>(null);
  readonly rfqId = signal('');
  readonly error = signal('');
  readonly busy = signal(false);
  readonly selectedContext = signal<{
    id: string;
    name: string;
    product: string;
    category: string;
    marketplace: string;
    market: string;
    currency: string;
    budget: string;
    verification: string;
  } | null>(null);
  readonly supplierOptions = signal<Array<{ id: string; name: string }>>([]);
  readonly requirement = {
    product_id: '',
    opportunity_id: '',
    payload: { category: '', target_quantity: 1, target_market: '', maximum_moq: null },
  };
  readonly rfq = { requirement_id: '', supplier_ids_text: '', title: 'Local sourcing request' };
  readonly quote = {
    rfq_id: '',
    supplier_id: '',
    quote_reference: '',
    currency: 'INR',
    unit_price: null as number | null,
    moq: null as number | null,
  };
  readonly sample = { rfq_id: '', supplier_id: '', quantity: 1 };
  readonly scenario = {
    requirement_id: '',
    inputs: {
      unit_supplier_price: null as number | null,
      freight: null as number | null,
      selling_price: null as number | null,
      quantity: 1,
    },
  };
  readonly decision = { requirement_id: '', quote_id: '', decision: 'hold', confirmed: false };
  constructor() {
    const params = this.route.snapshot.queryParamMap;
    const id = params.get('opportunity_id');
    if (id) {
      const supplierIds = (params.get('supplier_ids') ?? '')
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean);
      const context = {
        id,
        name: params.get('name') ?? '',
        product: params.get('product') ?? '',
        category: params.get('category') ?? '',
        marketplace: params.get('marketplace') ?? '',
        market: params.get('market') ?? params.get('region') ?? '',
        currency: params.get('currency') ?? 'INR',
        budget: params.get('budget') ?? '',
        verification: params.get('verification') ?? 'Not yet verified',
      };
      this.selectedContext.set(context);
      this.supplierOptions.set(
        supplierIds.map((supplierId, index) => ({
          id: supplierId,
          name:
            params.get('supplier_names')?.split(',')[index]?.trim() ||
            'Shortlisted supplier ' + (index + 1),
        })),
      );
      this.requirement.opportunity_id = id;
      this.requirement.payload.category = context.category;
      this.requirement.payload.target_market = context.market || context.marketplace;
      this.quote.supplier_id = supplierIds[0] ?? '';
      this.sample.supplier_id = supplierIds[0] ?? '';
    }
    void this.load();
  }
  activateSection(event: Event, sectionId: string): void {
    event.preventDefault();
    document.getElementById(sectionId)?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }
  toggleSupplier(id: string): void {
    const ids = this.rfq.supplier_ids_text
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean);
    const next = ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id];
    this.rfq.supplier_ids_text = next.join(',');
  }
  supplierLabel(id: unknown): string {
    return (
      this.supplierOptions().find((supplier) => supplier.id === id)?.name || 'Supplier evidence'
    );
  }
  economicsQuery(): Record<string, string> {
    const context = this.selectedContext();
    return context
      ? {
          opportunity_id: context.id,
          product: context.product,
          marketplace: context.marketplace,
          market: context.market,
        }
      : {};
  }
  private async load(): Promise<void> {
    try {
      this.overview.set(await this.service.sourcingOverview());
      this.requirements.set(
        ((await this.service.sourcingRequirements())['items'] as Record<string, unknown>[]) ?? [],
      );
      const current = this.requirements()[0];
      if (!this.rfq.requirement_id && typeof current?.['id'] === 'string') {
        this.rfq.requirement_id = current['id'];
        this.scenario.requirement_id = current['id'];
        this.decision.requirement_id = current['id'];
      }
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
      const current = this.requirements()[0];
      if (typeof current?.['id'] === 'string') {
        this.rfq.requirement_id = current['id'];
        this.scenario.requirement_id = current['id'];
        this.decision.requirement_id = current['id'];
      }
    });
  }
  async createRFQ(): Promise<void> {
    if (!this.rfq.requirement_id) {
      const current = this.requirements()[0];
      this.rfq.requirement_id = typeof current?.['id'] === 'string' ? current['id'] : '';
    }
    if (!this.rfq.requirement_id || !this.rfq.supplier_ids_text) {
      this.error.set(
        'Confirm a requirement and select at least one shortlisted supplier before preparing an RFQ.',
      );
      return;
    }
    await this.run(async () => {
      const response = await this.service.createRFQ({
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
      if (typeof response['id'] === 'string') {
        this.rfqId.set(response['id']);
        this.quote.rfq_id = response['id'];
        this.sample.rfq_id = response['id'];
      }
    });
  }
  async createQuote(): Promise<void> {
    if (this.quote.unit_price === null || this.quote.moq === null) {
      this.error.set('Enter a supplier unit price and MOQ before recording a quote.');
      return;
    }
    this.quote.rfq_id ||= this.rfqId();
    if (!this.quote.rfq_id) {
      this.error.set('Prepare an RFQ before recording a supplier quote.');
      return;
    }
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
      const latest = this.quotes()[0];
      if (!this.decision.quote_id && typeof latest?.['id'] === 'string') {
        this.decision.quote_id = latest['id'];
      }
    });
  }
  async createSample(): Promise<void> {
    await this.run(async () => {
      await this.service.createSampleRequest(this.sample);
    });
  }
  async calculate(): Promise<void> {
    const inputs = this.scenario.inputs;
    if (
      inputs.unit_supplier_price === null ||
      inputs.freight === null ||
      inputs.selling_price === null
    ) {
      this.error.set(
        'Enter supplier price, freight, and selling price before calculating economics.',
      );
      return;
    }
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
