import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

export interface CatalogCostContext {
  id: string;
  product_id: string | null;
  product_opportunity_id: string | null;
  canonical_supplier_id: string | null;
  supplier_id: string | null;
  opportunity_id: string | null;
  base_currency: string | null;
  target_quantity: string | null;
  quantity_unit: string | null;
  created_at: string;
  status: string;
}
export interface CatalogCostCalculation {
  id: string;
  context_id: string;
  status: string;
  currency: string | null;
  total_included_cost: string | null;
  per_unit_cost: string | null;
  missing_inputs: string[];
  warnings: string[];
}
export interface CatalogCostAssumption {
  quantity: string;
  unit: string;
  currency: string;
  unitPrice: string;
  reason: string;
}

// Uses the existing immutable economic input/snapshot/calculation authority.
// No formulas, supplier claims, fees or approvals are implemented here.
@Injectable({ providedIn: 'root' })
export class CatalogCostEstimateService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiUrl}/intelligence/sourcing-economics`;
  private readonly options = { withCredentials: true } as const;
  private get<T>(suffix: string): Promise<T> {
    return firstValueFrom(this.http.get<T>(this.base + suffix, this.options));
  }
  private post<T>(suffix: string, body: unknown): Promise<T> {
    return firstValueFrom(this.http.post<T>(this.base + suffix, body, this.options));
  }
  async contexts(productId: string): Promise<CatalogCostContext[]> {
    const response = await this.get<{ items: CatalogCostContext[] }>('/contexts');
    return response.items.filter((context) => this.matches(context, productId));
  }
  matches(context: CatalogCostContext, productId: string): boolean {
    return (
      context.product_id === productId &&
      !context.product_opportunity_id &&
      !context.canonical_supplier_id &&
      !context.supplier_id &&
      !context.opportunity_id
    );
  }
  async read(
    productId: string,
    id: string,
  ): Promise<{
    context: CatalogCostContext;
    calculation: CatalogCostCalculation | null;
    quotes: Array<{ provenance: string; freshness: string; assumption_reason: string | null }>;
  }> {
    const details = await this.get<{
      context: CatalogCostContext;
      quotes: Array<{ provenance: string; freshness: string; assumption_reason: string | null }>;
    }>('/contexts/' + id);
    if (!this.matches(details.context, productId)) throw new Error('COST_PRODUCT_CONTEXT_MISMATCH');
    const calculations = await this.get<{ items: CatalogCostCalculation[] }>('/calculations');
    const latest = calculations.items.find((c) => c.context_id === id);
    if (!latest) return { ...details, calculation: null };
    const exact = await this.get<{
      calculation: CatalogCostCalculation;
      exact_amounts?: { total_included_cost: string | null; per_unit_cost: string | null };
    }>('/calculations/' + latest.id);
    if (exact.calculation.context_id !== id) throw new Error('COST_PRODUCT_CONTEXT_MISMATCH');
    return {
      ...details,
      calculation: {
        ...exact.calculation,
        total_included_cost: exact.exact_amounts?.total_included_cost ?? null,
        per_unit_cost: exact.exact_amounts?.per_unit_cost ?? null,
      },
    };
  }
  async estimate(productId: string, input: CatalogCostAssumption): Promise<string> {
    // Material changes create a new explicit scenario; identical retries reuse it.
    const bytes = new TextEncoder().encode(JSON.stringify([productId, input]));
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    const key =
      'catalog-estimate-' +
      Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
    const { context } = await this.post<{ context: CatalogCostContext }>('/contexts', {
      product_id: productId,
      base_currency: input.currency,
      target_quantity: input.quantity,
      quantity_unit: input.unit,
      idempotency_key: key,
    });
    if (!this.matches(context, productId)) throw new Error('COST_PRODUCT_CONTEXT_MISMATCH');
    await this.post('/quotes', {
      context_id: context.id,
      product_id: productId,
      idempotency_key: key + '-input',
      unit_price: input.unitPrice,
      currency: input.currency,
      unit_basis: 'PER_UNIT',
      provenance: 'ASSUMED',
      freshness: 'UNKNOWN',
      assumption_reason: input.reason,
      notes:
        'Seller-entered Catalog estimate, not a supplier quotation or verified financial evidence.',
    });
    const { snapshot } = await this.post<{ snapshot: { id: string } }>(
      '/snapshots?context_id=' + context.id,
      {},
    );
    await this.post('/snapshots/' + snapshot.id + '/calculate', {});
    return context.id;
  }
}
