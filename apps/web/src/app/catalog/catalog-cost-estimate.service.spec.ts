import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { CatalogCostEstimateService } from './catalog-cost-estimate.service';
import { vi } from 'vitest';

describe('Catalog cost authority scope', () => {
  const context = {
    id: 'context-a',
    product_id: 'product-a',
    product_opportunity_id: null,
    opportunity_id: null,
    supplier_id: null,
    canonical_supplier_id: null,
    base_currency: 'INR',
    target_quantity: '12',
    quantity_unit: 'each',
    status: 'DRAFT',
    created_at: '',
  };
  beforeEach(() =>
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }),
  );
  afterEach(() => TestBed.inject(HttpTestingController).verify());
  it('renders only authoritative exact amounts, not rounded legacy JSON numbers', async () => {
    const api = TestBed.inject(CatalogCostEstimateService),
      http = TestBed.inject(HttpTestingController);
    const pending = api.read('product-a', 'context-a');
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/sourcing-economics/contexts/context-a')
      .flush({ context, quotes: [] });
    await vi.waitFor(() => {
      http
        .expectOne('http://127.0.0.1:8000/api/v1/intelligence/sourcing-economics/calculations')
        .flush({ items: [{ id: 'calculation-a', context_id: 'context-a' }] });
    });
    await vi.waitFor(() => {
      http
        .expectOne(
          'http://127.0.0.1:8000/api/v1/intelligence/sourcing-economics/calculations/calculation-a',
        )
        .flush({
          calculation: {
            id: 'calculation-a',
            context_id: 'context-a',
            per_unit_cost: 9999999999,
            total_included_cost: 119999999988,
          },
          exact_amounts: {
            per_unit_cost: '9999999999.00000001',
            total_included_cost: '119999999988.00000012',
          },
        });
    });
    expect((await pending).calculation?.per_unit_cost).toBe('9999999999.00000001');
  });
  it('lists only the exact manual Product scope and never borrows a supplier/opportunity context', async () => {
    const api = TestBed.inject(CatalogCostEstimateService),
      http = TestBed.inject(HttpTestingController),
      pending = api.contexts('product-a');
    const request = http.expectOne(
      'http://127.0.0.1:8000/api/v1/intelligence/sourcing-economics/contexts',
    );
    expect(request.request.withCredentials).toBe(true);
    request.flush({
      items: [
        context,
        { ...context, id: 'other', product_id: 'product-b' },
        { ...context, id: 'op', product_opportunity_id: 'op-a' },
        { ...context, id: 'supplier', supplier_id: 'supplier-a' },
      ],
    });
    expect(await pending).toEqual([context]);
  });
  it('rejects an owned but mismatching product context before reading any calculation', async () => {
    const api = TestBed.inject(CatalogCostEstimateService),
      http = TestBed.inject(HttpTestingController),
      pending = api.read('product-b', 'context-a');
    http
      .expectOne('http://127.0.0.1:8000/api/v1/intelligence/sourcing-economics/contexts/context-a')
      .flush({ context, quotes: [] });
    await expect(pending).rejects.toThrow('COST_PRODUCT_CONTEXT_MISMATCH');
    http.expectNone('http://127.0.0.1:8000/api/v1/intelligence/sourcing-economics/calculations');
  });
});
