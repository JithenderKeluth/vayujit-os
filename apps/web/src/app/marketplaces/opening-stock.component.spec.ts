import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { AuthService } from '../auth/auth.service';
import { CatalogService } from '../catalog/catalog.service';
import { ProductService } from '../products/product.service';
import { MarketplaceService } from './marketplace.service';
import { OpeningStockComponent, wholeStock } from './opening-stock.component';

describe('Opening stock review and fail-closed retry', () => {
  const product = {
    id: '00000000-0000-0000-0000-000000000001',
    name: 'Synthetic counted item',
    sku: 'BASE',
    product_type: 'physical',
    status: 'draft',
    brand_name: 'Synthetic brand',
  };
  const variant = {
    id: '00000000-0000-0000-0000-000000000002',
    title: 'Blue',
    variant_key: 'blue',
    sku: 'BLUE',
    status: 'draft',
  };
  async function create() {
    sessionStorage.clear();
    const createInventoryItem = vi.fn();
    const canonicalInventory = vi.fn().mockResolvedValue([]);
    const getProduct = vi.fn().mockResolvedValue({ product, variants: [variant] });
    TestBed.configureTestingModule({
      imports: [OpeningStockComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { user: () => ({ id: 'synthetic-owner' }) } },
        {
          provide: ProductService,
          useValue: { list: vi.fn().mockResolvedValue({ items: [product], page: 1, pages: 1 }) },
        },
        { provide: CatalogService, useValue: { getProduct } },
        {
          provide: MarketplaceService,
          useValue: { canonicalInventory, createInventoryItem, inventoryLedger: vi.fn() },
        },
      ],
    });
    const fixture = TestBed.createComponent(OpeningStockComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    const component = fixture.componentInstance;
    await component.choose(product.id);
    component.quantity = 12;
    fixture.detectChanges();
    return { component, fixture, createInventoryItem, canonicalInventory, getProduct };
  }
  it('accepts only explicit bounded integer quantities, not unknown or coerced values', () => {
    for (const v of [0, 12, 2_000_000_000]) expect(wholeStock(v)).toBe(true);
    for (const v of [null, undefined, '', '1', false, -1, 0.5, NaN, Infinity, 2_000_000_001])
      expect(wholeStock(v)).toBe(false);
  });
  it('review never writes and preserves the seller variant, SKU and location', async () => {
    const { component: c, createInventoryItem } = await create();
    c.variantId = variant.id;
    c.sku = ' CUSTOM ';
    c.location = ' shelf ';
    await c.prepare();
    expect(c.review()).toMatchObject({
      variant_id: variant.id,
      internal_sku: 'CUSTOM',
      location_code: 'shelf',
      opening_quantity: 12,
    });
    expect(createInventoryItem).not.toHaveBeenCalled();
    await c.submit();
    expect(createInventoryItem).not.toHaveBeenCalled();
  });
  it('requires a count instead of treating missing quantity as zero', async () => {
    const { component: c } = await create();
    c.quantity = null;
    await c.prepare();
    expect(c.review()).toBeNull();
    expect(c.errors()['quantity']).toBeTruthy();
  });
  it('rejects an existing SKU/location while allowing separate locations', async () => {
    const { component: c, canonicalInventory } = await create();
    canonicalInventory.mockResolvedValue([
      { product_id: product.id, internal_sku: 'BASE', location_code: 'default' },
    ]);
    await c.prepare();
    expect(c.review()).toBeNull();
    expect(c.error()).toContain('already exist');
    c.location = 'separate';
    await c.prepare();
    expect(c.review()).not.toBeNull();
  });
  it('refreshes eligibility before review and rejects an archived variant', async () => {
    const { component: c, getProduct } = await create();
    c.variantId = variant.id;
    getProduct.mockResolvedValue({ product, variants: [{ ...variant, status: 'archived' }] });
    await c.prepare();
    expect(c.review()).toBeNull();
  });
  it('network failure retains the identical intent/key and requires reapproval', async () => {
    const { component: c, createInventoryItem } = await create();
    await c.prepare();
    const first = c.review();
    createInventoryItem.mockRejectedValue(new Error('Timeout'));
    c.confirmed = true;
    await c.submit();
    expect(c.uncertain()).toBe(true);
    expect(c.confirmed).toBe(false);
    c.edit();
    expect(c.review()).toEqual(first);
    c.confirmed = true;
    await c.submit();
    expect(createInventoryItem).toHaveBeenNthCalledWith(1, first);
    expect(createInventoryItem).toHaveBeenNthCalledWith(2, first);
    expect(c.saved()).toBeNull();
  });
  it('a definitive conflict permits correction but never displays success', async () => {
    const { component: c, createInventoryItem } = await create();
    await c.prepare();
    createInventoryItem.mockRejectedValue(
      new HttpErrorResponse({
        status: 409,
        error: { detail: 'An inventory item already exists.' },
      }),
    );
    c.confirmed = true;
    await c.submit();
    expect(c.uncertain()).toBe(false);
    expect(c.error()).toContain('already exists');
    expect(c.saved()).toBeNull();
    expect(JSON.parse(sessionStorage.getItem('vj-opening-synthetic-owner') || '{}').pending).toBe(
      false,
    );
    c.edit();
    expect(c.review()).toBeNull();
    expect(c.quantity).toBe(12);
  });
  it('serializes clicks while awaiting a confirmation response', async () => {
    const { component: c, createInventoryItem } = await create();
    await c.prepare();
    let reject: (error: Error) => void = () => undefined;
    createInventoryItem.mockImplementation(
      () =>
        new Promise((_resolve, rejectPromise) => {
          reject = rejectPromise;
        }),
    );
    c.confirmed = true;
    const first = c.submit();
    await c.submit();
    expect(createInventoryItem).toHaveBeenCalledTimes(1);
    reject(new Error('Offline'));
    await first;
    expect(c.busy()).toBe(false);
  });
  it('does not save if tab storage cannot preserve retry identity', async () => {
    const { component: c, createInventoryItem } = await create();
    await c.prepare();
    const storage = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('Blocked');
    });
    c.confirmed = true;
    await c.submit();
    expect(createInventoryItem).not.toHaveBeenCalled();
    storage.mockRestore();
  });
  it('a committed request with failed verification stays pending, not editable or successful', async () => {
    const { component: c, createInventoryItem, canonicalInventory } = await create();
    await c.prepare();
    createInventoryItem.mockResolvedValue({ id: 'persisted' });
    canonicalInventory.mockRejectedValue(new HttpErrorResponse({ status: 404 }));
    c.confirmed = true;
    await c.submit();
    expect(c.saved()).toBeNull();
    expect(c.uncertain()).toBe(true);
    c.edit();
    expect(c.review()).not.toBeNull();
    expect(JSON.parse(sessionStorage.getItem('vj-opening-synthetic-owner') || '{}').pending).toBe(
      true,
    );
  });
  it('associates count help/error without changing its accessible name', async () => {
    const { component: c, fixture } = await create();
    c.quantity = null;
    await c.prepare();
    fixture.detectChanges();
    const input = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>(
      '#opening-quantity',
    );
    expect(input?.labels?.[0].textContent?.trim()).toBe('Opening quantity');
    expect(input?.getAttribute('aria-describedby')).toBe('quantity-help quantity-error');
    expect(input?.getAttribute('aria-invalid')).toBe('true');
  });
  it('does not present a failed search as proof that no eligible products exist', async () => {
    const { component: c, fixture } = await create();
    c.products.set([]);
    vi.spyOn(TestBed.inject(ProductService), 'list').mockRejectedValue(new Error('Unavailable'));
    await c.findProducts();
    fixture.detectChanges();
    expect(c.error()).toContain('could not be loaded');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain(
      'No eligible products match',
    );
  });
});
