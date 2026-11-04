import { DatePipe } from '@angular/common';
import { Component, Input, OnChanges, inject, signal, output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { BrandSummary } from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import {
  OpportunityDecision,
  OpportunityDetail,
  ProductOpportunityService,
} from './product-opportunity.service';

@Component({
  selector: 'app-opportunity-next-actions',
  standalone: true,
  imports: [DatePipe, FormsModule, RouterLink],
  template: `<section aria-labelledby="product-next-title" class="next-actions">
    <h2 id="product-next-title">Your decision and next step</h2>
    <p>Selection means investigate further, not verified demand, profit or permission to buy.</p>
    <p role="status">{{ status() }}</p>
    @if (error()) {
      <p role="alert">{{ error() }}</p>
      <button type="button" (click)="reload()" [disabled]="busy()">Reload decision</button>
    }
    @if (!opportunity.current_assessment_id || blocked) {
      <p>This product needs a current assessment and matching goal context before a decision.</p>
    }
    <div class="actions">
      <button
        type="button"
        (click)="decide('shortlist')"
        [disabled]="busy() || !ready() || selected()"
      >
        Select for further investigation
      </button>
      <button
        type="button"
        (click)="decide('reject')"
        [disabled]="busy() || !ready() || history()[0]?.action === 'reject'"
      >
        Reject this product
      </button>
      @if (selected()) {
        <a
          routerLink="/intelligence/cross-marketplace"
          [queryParams]="{ opportunity_id: opportunity.id, goal_id: goalId }"
          >Continue toward suppliers</a
        >
      }
    </div>
    @if (recordedSelection() && !blocked) {
      @if (opportunity.product_id) {
        <p>
          An existing product identity is linked. Catalog preparation preserves it; it does not
          create another product.
        </p>
      }
      <details>
        <summary>Prepare this selected product in Catalog</summary>
        <p>
          A local draft preserves this opportunity and HUMAN decision. Prices, costs, stock and
          supplier evidence are not invented. Nothing is published.
        </p>
        @if (!brands().length) {
          <p>An owned, active brand is required for a new product.</p>
          <a routerLink="/brands">Set up your brand</a>
          <button type="button" (click)="reload()" [disabled]="busy()">
            Refresh available brands
          </button>
        }
        <label
          >Catalog brand
          <select name="catalogBrand" [(ngModel)]="brandId">
            <option value="">Choose an existing brand</option>
            @for (brand of brands(); track brand.id) {
              <option [value]="brand.id">{{ brand.name }}</option>
            }
          </select></label
        >
        <label
          ><input type="checkbox" name="confirmCatalog" [(ngModel)]="confirmed" />I confirm this
          creates or opens a local Catalog draft only.</label
        >
        <button
          type="button"
          (click)="convert()"
          [disabled]="busy() || !selected() || !confirmed || (!brandId && !opportunity.product_id)"
        >
          Create or open Catalog draft
        </button>
        @if (catalogId()) {
          <p role="status">Catalog draft saved. Commercial values remain UNKNOWN until entered.</p>
          <a [routerLink]="['/catalog', catalogId()]">Open saved Catalog product</a>
        }
      </details>
    }
    <details>
      <summary>Previous HUMAN decisions ({{ history().length }})</summary>
      @if (!history().length) {
        <p>No decisions recorded. Viewing a product does not select it.</p>
      }
      <ol>
        @for (decision of history(); track decision.id) {
          <li>
            {{ decision.action }} — {{ decision.created_at | date: 'medium' }}
            <p>{{ decision.rationale }}</p>
            @if (decision.assessment_id !== opportunity.current_assessment_id) {
              <p>Historical assessment; review the current evidence before deciding again.</p>
            }
          </li>
        }
      </ol>
    </details>
  </section>`,
  styles: [
    `
      .next-actions {
        border: 1px solid #c6d9dc;
        border-radius: 12px;
        background: #fff;
        padding: 1.25rem;
        margin: 1rem 0;
      }
      .actions {
        display: flex;
        gap: 0.75rem;
        flex-wrap: wrap;
      }
      button,
      a,
      summary {
        min-height: 44px;
      }
      button,
      select {
        padding: 0.65rem;
      }
      button {
        border: 1px solid #0d6374;
        border-radius: 6px;
        background: #fff;
        color: #074d5c;
        font: inherit;
        font-weight: 650;
        cursor: pointer;
      }
      button:not(:disabled):hover {
        background: #eaf4f5;
      }
      button:disabled {
        opacity: 0.6;
        cursor: not-allowed;
      }
      .actions a {
        color: #074d5c;
        padding: 0.65rem;
        border: 1px solid #0d6374;
        border-radius: 6px;
      }
      label {
        display: block;
        margin: 1rem 0;
      }
      select {
        max-width: 100%;
        display: block;
      }
      p,
      li {
        overflow-wrap: anywhere;
      }
      details {
        margin-top: 1rem;
      }
      :focus-visible {
        outline: 3px solid #b56900;
        outline-offset: 3px;
      }
    `,
  ],
})
export class OpportunityNextActionsComponent implements OnChanges {
  @Input({ required: true }) opportunity!: OpportunityDetail;
  @Input() goalId = '';
  @Input() blocked = false;
  readonly changed = output<void>();
  private readonly service = inject(ProductOpportunityService);
  private readonly brandService = inject(BrandService);
  readonly history = signal<OpportunityDecision[]>([]);
  readonly brands = signal<BrandSummary[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly loaded = signal(false);
  readonly catalogId = signal('');
  brandId = '';
  confirmed = false;
  private replayKey = '';
  private replayAction = '';
  ngOnChanges(): void {
    this.confirmed = false;
    this.catalogId.set('');
    this.history.set([]);
    this.loaded.set(false);
    void this.reload();
  }
  ready(): boolean {
    return (
      this.loaded() &&
      !this.error() &&
      !this.blocked &&
      !!this.opportunity.current_assessment_id &&
      this.opportunity.lifecycle_status !== 'archived'
    );
  }
  selected(): boolean {
    return this.ready() && this.recordedSelection();
  }
  recordedSelection(): boolean {
    const latest = this.history()[0];
    return (
      this.loaded() &&
      !this.blocked &&
      this.opportunity.lifecycle_status !== 'archived' &&
      latest?.action === 'shortlist' &&
      latest.assessment_id === this.opportunity.current_assessment_id
    );
  }
  status(): string {
    if (!this.loaded()) return 'Loading current HUMAN decision…';
    if (this.error())
      return 'Action not completed. Last saved HUMAN decision is retained; reload before continuing.';
    const latest = this.history()[0];
    if (!latest) return 'Not selected. Review the evidence before deciding.';
    if (latest.assessment_id !== this.opportunity.current_assessment_id)
      return 'Previous decision is stale for the current assessment.';
    return latest.action === 'shortlist'
      ? 'Selected for further investigation.'
      : latest.action === 'reject'
        ? 'Rejected. History is retained; select again only after explicit review.'
        : 'Current decision: ' + latest.action;
  }
  async reload(): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    const id = this.opportunity.id;
    try {
      const history = await this.service.decisions(id);
      if (id !== this.opportunity.id) return;
      this.history.set(history);
      this.loaded.set(true);
      const brands = await this.brandService.list({ status: 'active', pageSize: 100 });
      if (id === this.opportunity.id) this.brands.set(brands.items);
    } catch {
      if (id === this.opportunity.id)
        this.error.set('Decision or brand context could not be loaded. Reload before continuing.');
    } finally {
      this.busy.set(false);
    }
  }
  async decide(action: 'shortlist' | 'reject'): Promise<void> {
    if (this.busy() || !this.ready()) return;
    if (
      !globalThis.confirm(
        action === 'reject'
          ? 'Reject this product? Its evidence and earlier decisions remain in history.'
          : 'Select this product for further investigation? This is not approval to buy or publish.',
      )
    )
      return;
    if (this.replayAction !== action) {
      this.replayAction = action;
      this.replayKey = 'product-decision-' + crypto.randomUUID();
    }
    this.busy.set(true);
    this.error.set('');
    try {
      await this.service.decide(this.opportunity.id, this.opportunity.current_assessment_id!, {
        action,
        rationale: 'HUMAN reviewed the current product evidence: ' + action,
        idempotency_key: this.replayKey,
      });
      this.replayAction = '';
      this.changed.emit();
    } catch {
      this.error.set(
        'Decision not saved. It may be stale or conflicting. Reload current evidence; no approval is assumed.',
      );
    } finally {
      this.busy.set(false);
      if (!this.error()) await this.reload();
    }
  }
  async convert(): Promise<void> {
    if (
      this.busy() ||
      !this.selected() ||
      !this.confirmed ||
      (!this.brandId && !this.opportunity.product_id)
    )
      return;
    this.busy.set(true);
    this.error.set('');
    try {
      const result = await this.service.convert(this.opportunity.id, {
        ...(this.brandId ? { brand_id: this.brandId } : {}),
        ...(this.goalId ? { goal_id: this.goalId } : {}),
        idempotency_key: 'catalog-opportunity-' + this.opportunity.id,
      });
      this.catalogId.set(result.product.id);
    } catch {
      this.error.set(
        'Catalog draft not confirmed. Check the current HUMAN selection, brand and goal. Reload and retry safely.',
      );
    } finally {
      this.busy.set(false);
    }
  }
}
