import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { expect, vi } from 'vitest';
import { provideRouter } from '@angular/router';
import { BusinessEntitySelectorsComponent } from './business-entity-selectors.component';

describe('BusinessEntitySelectorsComponent', () => {
  it('requests the explicitly selected brand and clears previous product/media identities', async () => {
    TestBed.configureTestingModule({
      imports: [BusinessEntitySelectorsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(BusinessEntitySelectorsComponent);
    const c = fixture.componentInstance;
    const http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne((r) => r.url.endsWith('/products')).flush({ items: [] });
    await fixture.whenStable();
    c.brandId = 'old-brand';
    c.productId = 'old-product';
    c.artifactId = 'old-artifact';
    c.mediaIds = ['old-media'];
    const emitted: string[] = [];
    c.productIdChange.subscribe((v) => emitted.push(v));
    c.selectBrand('new-brand');
    const request = http.expectOne((r) => r.url.endsWith('/products'));
    expect(request.request.params.get('brand_id')).toBe('new-brand');
    expect(c.productId).toBe('');
    expect(c.artifactId).toBe('');
    expect(c.mediaIds).toEqual([]);
    expect(emitted).toEqual(['']);
    request.flush({ items: [{ id: 'new-product', name: 'New product' }] });
    await vi.waitFor(() => expect(c.loading()).toBe(false));
    expect(c.products().map((p) => p.id)).toEqual(['new-product']);
    http.verify();
  });
  it('ignores a late product response from a superseded brand selection', async () => {
    TestBed.configureTestingModule({
      imports: [BusinessEntitySelectorsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(BusinessEntitySelectorsComponent);
    const c = fixture.componentInstance;
    const http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne((r) => r.url.endsWith('/products')).flush({ items: [] });
    await fixture.whenStable();
    c.selectBrand('first');
    const first = http.expectOne((r) => r.params.get('brand_id') === 'first');
    c.selectBrand('second');
    const second = http.expectOne((r) => r.params.get('brand_id') === 'second');
    second.flush({ items: [{ id: 'second-product', name: 'Second' }] });
    await vi.waitFor(() => expect(c.loading()).toBe(false));
    first.flush({ items: [{ id: 'first-product', name: 'First' }] });
    await Promise.resolve();
    expect(c.products().map((p) => p.id)).toEqual(['second-product']);
    http.verify();
  });
  it('loads owner-scoped business labels and emits canonical ids', async () => {
    TestBed.configureTestingModule({
      imports: [BusinessEntitySelectorsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(BusinessEntitySelectorsComponent);
    const component = fixture.componentInstance;
    component.showBrand = true;
    const http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http
      .expectOne((request) => request.url.endsWith('/products'))
      .flush({
        items: [
          { id: 'product-1', name: 'Travel mug', sku: 'MUG-1', category: 'Home', status: 'active' },
        ],
        page: 1,
        page_size: 50,
        total: 1,
        pages: 1,
      });
    http
      .expectOne((request) => request.url.endsWith('/brands'))
      .flush({
        items: [{ id: 'brand-1', name: 'Heritage', status: 'active' }],
        page: 1,
        page_size: 50,
        total: 1,
        pages: 1,
      });
    await fixture.whenStable();
    fixture.detectChanges();
    const productChanges: string[] = [];
    component.productIdChange.subscribe((value) => productChanges.push(value));
    const productSelect = fixture.nativeElement.querySelector('select') as HTMLSelectElement;
    productSelect.value = 'product-1';
    productSelect.dispatchEvent(new Event('change'));
    expect(productChanges).toEqual(['product-1']);
    expect(fixture.nativeElement.textContent).toContain('Travel mug');
    expect(fixture.nativeElement.textContent).toContain('Heritage');
    http.verify();
  });
  it('explains active-only eligibility without claiming draft products do not exist', async () => {
    TestBed.configureTestingModule({
      imports: [BusinessEntitySelectorsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const f = TestBed.createComponent(BusinessEntitySelectorsComponent);
    f.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    const request = http.expectOne((r) => r.url.endsWith('/products'));
    expect(request.request.params.get('status')).toBe('active');
    request.flush({ items: [], total: 0, pages: 0, page: 1, page_size: 50 });
    await vi.waitFor(() => expect(f.componentInstance.loading()).toBe(false));
    f.detectChanges();
    const root = f.nativeElement as HTMLElement;
    expect(root.textContent).toContain('No active products available');
    expect(root.textContent).toContain('Draft and archived products are not eligible');
    expect(root.textContent).not.toContain('No products yet');
    expect(root.querySelector('a[href="/catalog"]')).not.toBeNull();
    http.verify();
  });
  it('shows failure rather than empty eligibility, then retries the canonical read', async () => {
    TestBed.configureTestingModule({
      imports: [BusinessEntitySelectorsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const f = TestBed.createComponent(BusinessEntitySelectorsComponent);
    f.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http
      .expectOne((r) => r.url.endsWith('/products'))
      .flush({}, { status: 503, statusText: 'Unavailable' });
    await vi.waitFor(() => expect(f.componentInstance.loading()).toBe(false));
    f.detectChanges();
    expect(f.nativeElement.textContent).not.toContain('No active products available');
    const retry = f.componentInstance.loadContext();
    http
      .expectOne((r) => r.url.endsWith('/products'))
      .flush({ items: [], total: 0, pages: 0, page: 1, page_size: 50 });
    await retry;
    f.detectChanges();
    expect(f.nativeElement.textContent).toContain('No active products available');
    http.verify();
  });
});
