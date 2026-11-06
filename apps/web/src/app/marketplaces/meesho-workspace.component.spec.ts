import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute } from '@angular/router';
import { TestBed } from '@angular/core/testing';

import { MeeshoWorkspaceComponent } from './meesho-workspace.component';

describe('MeeshoWorkspaceComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MeeshoWorkspaceComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => null } } } },
      ],
    }).compileComponents();
  });

  function createComponent() {
    return TestBed.createComponent(MeeshoWorkspaceComponent).componentInstance;
  }
  it('exposes listing-editor controls as a named group, not an unnamed generic container', async () => {
    const fixture = TestBed.createComponent(MeeshoWorkspaceComponent);
    vi.spyOn(fixture.componentInstance, 'ngOnInit').mockImplementation(() => undefined);
    fixture.componentInstance.activeListing.set({
      id: 'l',
      title: 'Synthetic draft',
      marketplace_sku: 'QA7',
      status: 'draft',
      publication_state: 'draft',
      remote_listing_id: null,
    });
    fixture.detectChanges();
    await fixture.whenStable();
    expect(
      (fixture.nativeElement as HTMLElement)
        .querySelector('[aria-label="Listing editor sections"]')
        ?.getAttribute('role'),
    ).toBe('group');
  });
  it('preserves exact listing account/product context for local preparation', () => {
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
    expect(component.listingDraft.artifact_id).toBe('exact-artifact');
  });
  it('unwraps canonical paginated Products and Brands before rendering options', async () => {
    const c = createComponent(),
      http = TestBed.inject(HttpTestingController);
    const pending = c.loadWorkspace();
    http.expectOne((r) => r.url.endsWith('/meesho/accounts')).flush([]);
    http.expectOne((r) => r.url.endsWith('/meesho/listings')).flush([]);
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

  it('does not submit a price while its persisted listing inputs are still loading', () => {
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
    const premature = http.match((r) => r.method === 'PUT');
    for (const request of premature) request.flush({}, { status: 422, statusText: 'Incomplete' });
    expect(premature).toHaveLength(0);
  });

  it('ignores a late response for a listing that is no longer selected', async () => {
    const c = createComponent(),
      http = TestBed.inject(HttpTestingController);
    const draft = (id: string) => ({
      id,
      account_id: id + '-account',
      title: 'Synthetic ' + id,
      marketplace_sku: id,
      status: 'draft',
      publication_state: 'draft',
      remote_listing_id: null,
    });
    c.selectListing(draft('a'));
    c.selectListing(draft('b'));
    const hydrate = async (id: string, amount: string) => {
      for (let turn = 0; turn < 12; turn++) {
        for (const request of http.match(
          (r) =>
            r.url.includes('/accounts/' + id + '-account/') ||
            r.url.includes('/listings/' + id + '/'),
        )) {
          request.flush(
            request.request.url.endsWith('/pricing')
              ? { selling_price: amount, list_price: '150', sale_price: null, currency: 'INR' }
              : request.request.url.endsWith('/readiness')
                ? { ready: true, blocking: [] }
                : [],
          );
        }
        await Promise.resolve();
        await Promise.resolve();
      }
    };
    await hydrate('b', '20.25');
    await hydrate('a', '10.25');
    expect(c.activeListing()?.id).toBe('b');
    expect(c.priceDraft.selling_price).toBe(20.25);
    http.verify();
  });

  it('preserves matching values and rejects matrices above 100 rows', () => {
    const component = createComponent();
    component.matrixDimensionsText = 'Color=Red|Blue';
    component.buildVariantMatrix();
    component.variants()[0].sku = 'MS-RED';
    component.matrixDimensionsText = 'Color=Red|Blue|Green';
    component.buildVariantMatrix();
    expect(component.variants()[0].sku).toBe('MS-RED');
    component.matrixDimensionsText = 'A=1|2|3|4|5|6|7|8|9|10;B=1|2|3|4|5|6|7|8|9|10;C=1|2';
    component.buildVariantMatrix();
    expect(component.matrixError()).toContain('at most 100');
  });
});
