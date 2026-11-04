import { DatePipe } from '@angular/common';
import { Component, DestroyRef, Input, OnChanges, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { SellerMoneyPipe } from '../intelligence/seller-financial-format';
import { CatalogCostEstimateService, CatalogCostContext } from './catalog-cost-estimate.service';

@Component({
  selector: 'app-catalog-cost-estimate',
  imports: [DatePipe, FormsModule, SellerMoneyPipe],
  template: `<section class="card" aria-labelledby="manual-cost-title">
    <h2 id="manual-cost-title">Known-cost estimate for this Catalog product</h2>
    <p>
      No research lineage is needed. Enter an explicit seller assumption; this does not create a
      supplier quotation or verified cost. Stock, listing approval and procurement are unchanged.
    </p>
    <p>
      Freight, fees, GST/tax, returns, advertising and other unentered costs remain UNKNOWN, not
      zero. This is not full landed cost, net profit, margin or commercial readiness.
    </p>
    @if (error()) {
      <p role="alert">{{ error() }}</p>
    }
    @if (loading()) {
      <p role="status">Loading saved cost scenarios…</p>
    }
    <label for="catalog-cost-scenario">Saved product cost scenario</label>
    <select
      id="catalog-cost-scenario"
      name="catalog-cost-scenario"
      [ngModel]="selected()"
      (ngModelChange)="choose($event)"
      [disabled]="busy() || loading()"
    >
      <option value="">Choose a saved estimate</option>
      @for (context of contexts(); track context.id) {
        <option [value]="context.id">
          {{ context.created_at | date: 'medium' }} · {{ context.target_quantity }}
          {{ context.quantity_unit }} · {{ context.base_currency || 'UNKNOWN' }}
        </option>
      }
    </select>
    @if (saved(); as evidence) {
      <div class="estimate" role="status">
        <h3>Saved historical estimate — not verified profitability</h3>
        <p>
          Context {{ evidence.context.id }} · {{ evidence.context.status }} ·
          {{ evidence.context.target_quantity }} {{ evidence.context.quantity_unit }}
        </p>
        @if (evidence.calculation; as calculation) {
          <dl>
            <dt>Known-cost subtotal</dt>
            <dd>{{ calculation.total_included_cost | sellerMoney: calculation.currency }}</dd>
            <dt>Known cost per {{ evidence.context.quantity_unit }}</dt>
            <dd>{{ calculation.per_unit_cost | sellerMoney: calculation.currency }}</dd>
            <dt>Calculation state</dt>
            <dd>{{ calculation.status }} — not launch readiness</dd>
          </dl>
          <p>
            Missing inputs:
            {{ calculation.missing_inputs.join(', ') || 'See excluded costs above' }}.
          </p>
          @for (warning of calculation.warnings; track $index) {
            <p>{{ warning }}</p>
          }
        } @else {
          <p>
            No completed calculation in this scenario. Re-enter the same assumptions below to safely
            resume; no result is assumed.
          </p>
        }
        @for (quote of evidence.quotes; track $index) {
          <p>
            Input provenance: {{ quote.provenance }} · Freshness: {{ quote.freshness }} ·
            {{ quote.assumption_reason }}
          </p>
        }
        <p>
          Historical inputs are not a claim of current supplier terms. If assumptions change, save a
          new estimate below; earlier results remain in history.
        </p>
      </div>
    }
    <form (ngSubmit)="save()" aria-label="Seller cost assumptions">
      <fieldset [disabled]="busy()">
        <legend>New or identical-retry cost scenario</legend>
        <label
          >Planned quantity<input
            name="estimate-quantity"
            [(ngModel)]="quantity"
            inputmode="decimal"
            required
        /></label>
        <label
          >Quantity unit<input name="estimate-unit" [(ngModel)]="unit" maxlength="40" required
        /></label>
        <label
          >Assumed acquisition cost per unit<input
            name="estimate-price"
            [(ngModel)]="unitPrice"
            inputmode="decimal"
            required
        /></label>
        <label
          >Estimate currency<input
            name="estimate-currency"
            [(ngModel)]="currency"
            maxlength="3"
            required
        /></label>
        <label
          >Assumption basis and limitations<textarea
            name="estimate-reason"
            [(ngModel)]="reason"
            maxlength="4000"
            required
          ></textarea>
        </label>
        <button type="submit" [disabled]="busy()">
          {{ busy() ? 'Saving canonical estimate…' : 'Save known-cost estimate' }}
        </button>
      </fieldset>
    </form>
  </section>`,
  styles: [
    `
      :host {
        display: block;
        margin-bottom: 1.5rem;
      }
      label {
        display: grid;
        gap: 0.35rem;
        margin: 0.75rem 0;
      }
      input,
      select,
      textarea {
        width: 100%;
        min-width: 0;
        padding: 0.65rem;
        font: inherit;
        color: var(--vj-color-ink);
        background: var(--vj-color-surface);
        border: 1px solid var(--vj-color-border);
        border-radius: 0.4rem;
      }
      fieldset {
        min-width: 0;
        border: 1px solid var(--vj-color-border);
        padding: 1rem;
      }
      .estimate {
        margin: 1rem 0;
        padding: 1rem;
        background: var(--vj-color-surface-muted);
      }
      dd,
      p {
        overflow-wrap: anywhere;
      }
      dd {
        margin-left: 0;
      }
      button {
        min-height: 2.75rem;
      }
    `,
  ],
})
export class CatalogCostEstimateComponent implements OnChanges {
  @Input({ required: true }) productId = '';
  private readonly api = inject(CatalogCostEstimateService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  readonly contexts = signal<CatalogCostContext[]>([]);
  readonly saved = signal<Awaited<ReturnType<CatalogCostEstimateService['read']>> | null>(null);
  readonly selected = signal('');
  readonly busy = signal(false);
  readonly loading = signal(false);
  readonly error = signal('');
  quantity = '';
  unit = 'each';
  unitPrice = '';
  currency = 'INR';
  reason = '';
  private epoch = 0;
  constructor() {
    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      if (this.productId) void this.load(params.get('cost_context_id') || '');
    });
  }
  ngOnChanges(): void {
    this.quantity = '';
    this.unitPrice = '';
    this.reason = '';
    void this.load(this.route.snapshot.queryParamMap.get('cost_context_id') || '');
  }
  async load(id: string): Promise<void> {
    const epoch = ++this.epoch,
      productId = this.productId;
    this.loading.set(true);
    this.error.set('');
    this.saved.set(null);
    this.selected.set('');
    this.contexts.set([]);
    try {
      const contexts = await this.api.contexts(productId);
      if (epoch !== this.epoch || this.destroyRef.destroyed) return;
      this.contexts.set(contexts);
      if (id) {
        if (!contexts.some((c) => c.id === id)) throw new Error('CONTEXT_MISMATCH');
        const saved = await this.api.read(productId, id);
        if (epoch === this.epoch) {
          this.saved.set(saved);
          this.selected.set(id);
        }
      }
    } catch {
      if (epoch === this.epoch)
        this.error.set(
          'This saved estimate is unavailable or does not match this product. Choose an owned product scenario or retry. No cost basis was substituted.',
        );
    } finally {
      if (epoch === this.epoch) this.loading.set(false);
    }
  }
  async choose(id: string): Promise<void> {
    if (this.busy()) return;
    await this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { cost_context_id: id || null },
      queryParamsHandling: 'merge',
      preserveFragment: true,
    });
  }
  async save(): Promise<void> {
    if (this.busy()) return;
    const input = {
      quantity: this.quantity.trim(),
      unit: this.unit.trim(),
      unitPrice: this.unitPrice.trim(),
      currency: this.currency.trim().toUpperCase(),
      reason: this.reason.trim(),
    };
    const decimal = /^(?:0|[1-9]\d{0,9})(?:\.\d{1,8})?$/;
    if (
      !decimal.test(input.quantity) ||
      !/[1-9]/.test(input.quantity) ||
      !decimal.test(input.unitPrice) ||
      !input.unit ||
      input.unit.length > 40 ||
      !/^[A-Z]{3}$/.test(input.currency) ||
      !input.reason ||
      input.reason.length > 4000
    ) {
      this.error.set(
        'Enter a positive quantity, an explicit non-negative unit cost, unit, three-letter currency and assumption basis. Unknown cost must stay blank; it cannot be calculated.',
      );
      return;
    }
    const productId = this.productId;
    this.busy.set(true);
    this.error.set('');
    try {
      const id = await this.api.estimate(productId, input);
      if (productId !== this.productId || this.destroyRef.destroyed) return;
      await this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { cost_context_id: id },
        queryParamsHandling: 'merge',
        preserveFragment: true,
      });
      await this.load(id);
    } catch {
      if (productId === this.productId)
        this.error.set(
          'Estimate was not confirmed. No readiness is assumed. Retry identical assumptions to resume safely; changed assumptions create a separate scenario.',
        );
    } finally {
      this.busy.set(false);
    }
  }
}
