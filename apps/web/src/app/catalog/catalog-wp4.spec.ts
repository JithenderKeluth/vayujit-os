import { HttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter, Router } from '@angular/router';
import { BehaviorSubject, of } from 'rxjs';
import { vi } from 'vitest';
import { CatalogService } from './catalog.service';
import { CatalogWorkspaceComponent } from './catalog-workspace.component';
import { CatalogCostEstimateComponent } from './catalog-cost-estimate.component';
import { CatalogCostEstimateService } from './catalog-cost-estimate.service';
import { ProductService } from '../products/product.service';
import { ProductChannelViewComponent } from '../marketplaces/product-channel-view.component';
import { MarketplaceService } from '../marketplaces/marketplace.service';

const product = {
  id: 'product-a',
  name: 'Synthetic A',
  status: 'draft',
  sku: 'QA-A',
  brand_name: 'QA',
};
function detail(id = 'product-a') {
  return {
    product: { ...product, id, name: id === 'product-a' ? 'Synthetic A' : 'Synthetic B' },
    lineage: { opportunity_id: 'op-a', provenance_json: {} },
    variants: [],
    images: [],
    supplier_associations: [],
    listing_drafts: [],
  };
}
function route() {
  const params = new BehaviorSubject(convertToParamMap({ id: 'product-a' }));
  const queries = new BehaviorSubject(convertToParamMap({}));
  return {
    paramMap: params,
    queryParamMap: queries,
    snapshot: { paramMap: params.value, queryParamMap: queries.value },
  };
}
async function catalog() {
  const r = route();
  const api = {
    getProduct: vi.fn().mockResolvedValue(detail()),
    readiness: vi.fn().mockResolvedValue(null),
    media: vi.fn().mockResolvedValue({ items: [] }),
    economics: vi.fn().mockResolvedValue({ available: false }),
    createVariant: vi.fn(),
    createListingDraft: vi.fn(),
  };
  TestBed.configureTestingModule({
    imports: [CatalogWorkspaceComponent],
    providers: [
      provideRouter([]),
      { provide: ActivatedRoute, useValue: r },
      { provide: CatalogService, useValue: api },
      { provide: ProductService, useValue: {} },
    ],
  });
  const f = TestBed.createComponent(CatalogWorkspaceComponent);
  await f.whenStable();
  f.detectChanges();
  return { f, c: f.componentInstance, api, r, root: f.nativeElement as HTMLElement };
}
describe('WP4 Catalog recovery and product scope', () => {
  it('selects a returned owned ready upload after asynchronous options render without attaching it', async () => {
    const { c, f, api, r, root } = await catalog();
    r.snapshot.queryParamMap = convertToParamMap({ media_id: 'media-a' });
    api.media.mockResolvedValue({
      items: [
        {
          id: 'media-a',
          status: 'ready',
          mime_type: 'image/png',
          original_filename: 'Synthetic.png',
          preview_url: '/private',
        },
      ],
    });
    await c.loadMediaAssets();
    f.detectChanges();
    await f.whenStable();
    expect((root.querySelector('.asset-picker select') as HTMLSelectElement).value).toBe('media-a');
    expect(c.images()).toEqual([]);
  });
  it('retains loaded context, form values and h1 after invalid variant JSON', async () => {
    const { c, f, root, api } = await catalog();
    c.newVariantKey = 'blue';
    c.newVariantOptions = '{invalid';
    await c.addVariant();
    f.detectChanges();
    expect(root.querySelector('h1')?.textContent).toContain('Synthetic A');
    expect(root.querySelector('#identity-title')).not.toBeNull();
    expect(root.querySelector('[role=alert]')?.textContent).toContain('Change not completed');
    expect(c.newVariantOptions).toBe('{invalid');
    expect(api.createVariant).not.toHaveBeenCalled();
  });
  it('rejects array options without discarding the loaded product', async () => {
    const { c, api } = await catalog();
    c.newVariantOptions = '[]';
    await c.addVariant();
    expect(c.error()).toContain('valid JSON');
    expect(c.detail()?.product.id).toBe(product.id);
    expect(api.createVariant).not.toHaveBeenCalled();
  });
  it('keeps server mutation errors inline and prevents duplicate pending draft requests', async () => {
    const { c, api, f, root } = await catalog();
    let reject!: (reason: Error) => void;
    api.createListingDraft.mockImplementation(
      () =>
        new Promise((_, r) => {
          reject = r;
        }),
    );
    const first = c.createDraft('amazon_in');
    await c.createDraft('amazon_in');
    expect(api.createListingDraft).toHaveBeenCalledTimes(1);
    reject(new Error('synthetic'));
    await first;
    f.detectChanges();
    expect(root.querySelector('h1')).not.toBeNull();
    expect(c.detail()?.product.id).toBe(product.id);
    expect(c.draftSaving()).toBeNull();
  });
  it('offers upload with exact return identity and distinguishes empty from unavailable media', async () => {
    const { c, api, f, root } = await catalog();
    expect(root.querySelector('a[href*="catalog_product_id=product-a"]')).not.toBeNull();
    expect(root.textContent).toContain('No ready images');
    api.media.mockRejectedValue(new Error('synthetic'));
    await c.loadMediaAssets();
    f.detectChanges();
    expect(c.mediaError()).toContain('could not be loaded');
    expect(root.textContent).not.toContain('No ready images');
  });
  it('resets the product on reused routes and ignores late reads from the previous product', async () => {
    const { c, api, r, f } = await catalog();
    let old!: (d: ReturnType<typeof detail>) => void;
    api.getProduct.mockImplementation((id: string) =>
      id === 'product-a'
        ? new Promise((resolve) => {
            old = resolve;
          })
        : Promise.resolve(detail(id)),
    );
    const pending = c.loadDetail();
    r.paramMap.next(convertToParamMap({ id: 'product-b' }));
    await f.whenStable();
    old(detail('product-a'));
    await pending;
    expect(c.selectedId).toBe('product-b');
    expect(c.detail()?.product.name).toBe('Synthetic B');
  });
});

describe('WP4 manual-product known-cost assumptions', () => {
  async function create() {
    const r = route(),
      api = {
        contexts: vi.fn().mockResolvedValue([]),
        read: vi.fn(),
        estimate: vi.fn().mockResolvedValue('context-a'),
      };
    TestBed.configureTestingModule({
      imports: [CatalogCostEstimateComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: r },
        { provide: CatalogCostEstimateService, useValue: api },
      ],
    });
    const f = TestBed.createComponent(CatalogCostEstimateComponent);
    f.componentRef.setInput('productId', 'product-a');
    f.detectChanges();
    await f.whenStable();
    return { f, c: f.componentInstance, api, r };
  }
  it('does not navigate back to an old product when its pending save finishes after leaving', async () => {
    const { c, f, api } = await create();
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    let resolve!: (id: string) => void;
    api.estimate.mockImplementation(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    c.quantity = '12';
    c.unitPrice = '100.125';
    c.reason = 'Synthetic';
    const pending = c.save();
    f.destroy();
    resolve('old-context');
    await pending;
    expect(navigate).not.toHaveBeenCalled();
  });
  it('never calculates missing acquisition cost as zero', async () => {
    const { c, api } = await create();
    c.quantity = '12';
    c.reason = 'Synthetic assumption';
    await c.save();
    expect(api.estimate).not.toHaveBeenCalled();
    expect(c.error()).toContain('Unknown cost must stay blank');
  });
  it('allows an explicitly entered zero, labels assumptions and uses the canonical engine', async () => {
    const { c, api } = await create();
    c.quantity = '12';
    c.unitPrice = '0';
    c.reason = 'Explicit synthetic no-cost assumption';
    await c.save();
    expect(api.estimate).toHaveBeenCalledWith(
      'product-a',
      expect.objectContaining({ unitPrice: '0', currency: 'INR', reason: c.reason }),
    );
  });
  it('rejects a foreign/stale cost scenario instead of substituting the only owned context', async () => {
    const { c, api } = await create();
    api.contexts.mockResolvedValue([{ id: 'owned-a', product_id: 'product-a' }]);
    await c.load('foreign-b');
    expect(c.saved()).toBeNull();
    expect(c.error()).toContain('does not match');
    expect(api.read).not.toHaveBeenCalled();
  });
  it('disables duplicate saves while the canonical estimate is pending', async () => {
    const { c, api } = await create();
    let resolve!: (id: string) => void;
    api.estimate.mockImplementation(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    c.quantity = '12';
    c.unitPrice = '100.125';
    c.reason = 'Synthetic';
    const first = c.save();
    await c.save();
    expect(api.estimate).toHaveBeenCalledTimes(1);
    resolve('context-a');
    await first;
  });
});

describe('WP4 marketplace preparation is not channel-wide financial attribution', () => {
  it('shows both disconnected destinations and UNKNOWN product finances without reading unrelated orders or settlements', async () => {
    const r = route(),
      api = {
        accounts: vi.fn().mockResolvedValue([]),
        listings: vi
          .fn()
          .mockResolvedValue([
            { id: 'unrelated', product_id: 'product-b', marketplace: 'shopify' },
          ]),
        inventory: vi.fn().mockResolvedValue([]),
        productChannelIntelligence: vi.fn().mockResolvedValue([
          { channel: 'amazon_in', readiness: 'BLOCKED', blockers: [] },
          { channel: 'website', readiness: 'NOT_EVALUATED', blockers: [] },
        ]),
        orders: vi.fn(),
        settlements: vi.fn(),
      };
    TestBed.configureTestingModule({
      imports: [ProductChannelViewComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: r },
        { provide: MarketplaceService, useValue: api },
        { provide: CatalogService, useValue: { getProduct: vi.fn().mockResolvedValue(detail()) } },
        { provide: HttpClient, useValue: { get: () => of({ channels: [] }) } },
      ],
    });
    const f = TestBed.createComponent(ProductChannelViewComponent);
    await f.whenStable();
    f.detectChanges();
    const root = f.nativeElement as HTMLElement;
    expect(f.componentInstance.channels().map((c) => c.marketplace)).toEqual([
      'amazon',
      'flipkart',
    ]);
    expect(root.textContent).toContain('Not connected');
    expect(root.textContent).toContain('profit are UNKNOWN');
    expect(api.orders).not.toHaveBeenCalled();
    expect(api.settlements).not.toHaveBeenCalled();
    expect(f.componentInstance.contentDestinations().map((c) => c.channel)).toEqual(['website']);
    expect(root.querySelector('a[href="/catalog/product-a#drafts-title"]')).not.toBeNull();
    r.paramMap.next(convertToParamMap({ id: 'product-b' }));
    await f.whenStable();
    expect(f.componentInstance.productId).toBe('product-b');
  });
});
