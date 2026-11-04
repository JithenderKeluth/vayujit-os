import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute } from '@angular/router';
import { TestBed } from '@angular/core/testing';

import { FlipkartWorkspaceComponent } from './flipkart-workspace.component';

describe('FlipkartWorkspaceComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FlipkartWorkspaceComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => null } } } },
      ],
    }).compileComponents();
  });

  function createComponent() {
    return TestBed.createComponent(FlipkartWorkspaceComponent).componentInstance;
  }
  it('unwraps canonical paginated Products and Brands before rendering options', async () => {
    const c = createComponent(),
      http = TestBed.inject(HttpTestingController);
    const pending = c.loadWorkspace();
    http.expectOne((r) => r.url.endsWith('/flipkart/accounts')).flush([]);
    http.expectOne((r) => r.url.endsWith('/flipkart/listings')).flush([]);
    await Promise.resolve();
    await Promise.resolve();
    http
      .expectOne((r) => r.url.endsWith('/products'))
      .flush({ items: [{ id: 'p', name: 'Product' }], total: 1 });
    await Promise.resolve();
    await Promise.resolve();
    http
      .expectOne((r) => r.url.endsWith('/brands'))
      .flush({ items: [{ id: 'b', name: 'Brand' }], total: 1 });
    await pending;
    expect(c.products().map((x) => x.id)).toEqual(['p']);
    expect(c.brands().map((x) => x.id)).toEqual(['b']);
    http.verify();
  });
  it('builds deterministic six-row matrix for three sizes and two colors', () => {
    const component = createComponent();
    component.matrixDimensionsText = 'Size=S|M|L;Color=Red|Blue';
    component.buildVariantMatrix();
    expect(component.variants().map((row) => row.options)).toEqual([
      'Size=S, Color=Red',
      'Size=S, Color=Blue',
      'Size=M, Color=Red',
      'Size=M, Color=Blue',
      'Size=L, Color=Red',
      'Size=L, Color=Blue',
    ]);
    expect(new Set(component.variants().map((row) => row.stable_variant_key)).size).toBe(6);
  });

  it('preserves matching values and rejects matrices above 100 rows', () => {
    const component = createComponent();
    component.matrixDimensionsText = 'Color=Red|Blue';
    component.buildVariantMatrix();
    component.variants()[0].sku = 'FK-RED';
    component.matrixDimensionsText = 'Color=Red|Blue|Green';
    component.buildVariantMatrix();
    expect(component.variants()[0].sku).toBe('FK-RED');
    component.matrixDimensionsText = 'A=1|2|3|4|5|6|7|8|9|10;B=1|2|3|4|5|6|7|8|9|10;C=1|2';
    component.buildVariantMatrix();
    expect(component.matrixError()).toContain('at most 100');
  });
  it('pins exact saved listing context instead of substituting another account', () => {
    const component = createComponent();
    vi.spyOn(component, 'loadListingData').mockResolvedValue();
    component.selectListing({
      id: 'l',
      account_id: 'exact-account',
      product_id: 'exact-product',
      brand_id: 'exact-brand',
      content_artifact_id: 'exact-artifact',
      title: 'Synthetic draft',
      marketplace_sku: 'QA7',
      status: 'draft',
      publication_state: 'draft',
      remote_listing_id: null,
    });
    expect(component.listingDraft.account_id).toBe('exact-account');
    expect(component.listingDraft.product_id).toBe('exact-product');
    expect(component.listingDraft.brand_id).toBe('exact-brand');
    expect(component.listingDraft.artifact_id).toBe('exact-artifact');
  });
  it('does not submit a price before the exact listing inputs finish loading', () => {
    const c = createComponent(),
      http = TestBed.inject(HttpTestingController);
    c.selectListing({
      id: 'a',
      account_id: 'a-account',
      title: 'Synthetic A',
      marketplace_sku: 'A',
      status: 'draft',
      publication_state: 'draft',
      remote_listing_id: null,
    });
    c.priceDraft.selling_price = 100.25;
    void c.savePrice();
    http.expectNone((r) => r.method === 'PUT');
  });

  it('refreshes authoritative readiness after local price save without submitting', async () => {
    const component = createComponent(),
      http = TestBed.inject(HttpTestingController);
    component.activeListing.set({
      id: 'l',
      title: 'Synthetic draft',
      marketplace_sku: 'QA7',
      status: 'draft',
      publication_state: 'draft',
      remote_listing_id: null,
    });
    component.readiness.set({ ready: false, blocking: [{ message: 'Price missing' }] });
    component.priceDraft.selling_price = 100.25;
    const pending = component.savePrice();
    http
      .expectOne((r) => r.url.endsWith('/listings/l/pricing'))
      .flush({ draft: true, amount: '100.25' });
    await Promise.resolve();
    await Promise.resolve();
    http
      .expectOne((r) => r.url.endsWith('/listings/l/readiness'))
      .flush({ ready: true, blocking: [] });
    await pending;
    expect(component.readiness()?.ready).toBe(true);
    expect(component.message()).toContain('Not submitted or published');
    http.expectNone((r) => r.url.includes('/submit'));
    http.verify();
  });
});
