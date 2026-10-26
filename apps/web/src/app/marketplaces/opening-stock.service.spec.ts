import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { InventoryOpeningRequest, MarketplaceService } from './marketplace.service';

describe('Opening stock canonical HTTP transport', () => {
  const payload: InventoryOpeningRequest = {
    product_id: 'synthetic-product',
    variant_id: null,
    internal_sku: 'COUNTED',
    location_code: 'default',
    unit: 'each',
    opening_quantity: 0,
    low_stock_threshold: 0,
    idempotency_key: 'ui-opening-synthetic-key',
  };
  function setup() {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    return {
      service: TestBed.inject(MarketplaceService),
      http: TestBed.inject(HttpTestingController),
    };
  }
  it('posts the immutable reviewed payload with authenticated cookies, not a marketplace call', async () => {
    const { service, http } = setup();
    const result = service.createInventoryItem(payload);
    const request = http.expectOne((r) => r.url.endsWith('/inventory/items'));
    expect(request.request.method).toBe('POST');
    expect(request.request.withCredentials).toBe(true);
    expect(request.request.body).toEqual(payload);
    request.flush({ id: 'saved-id' });
    expect(await result).toEqual({ id: 'saved-id' });
    http.verify();
  });
  it('bounds a hung confirmation at twenty seconds without silently retrying', async () => {
    vi.useFakeTimers();
    try {
      const { service, http } = setup();
      const result = service.createInventoryItem(payload);
      const outcome = result.then(
        () => {
          throw new Error('Unexpected confirmation success');
        },
        (error: unknown) => error,
      );
      const request = http.expectOne((r) => r.url.endsWith('/inventory/items'));
      await vi.advanceTimersByTimeAsync(20_000);
      expect(await outcome).toMatchObject({ name: 'TimeoutError' });
      expect(request.cancelled).toBe(true);
      http.verify();
    } finally {
      vi.useRealTimers();
    }
  });
  it('preserves authoritative conflict responses without retries or successful fallback', async () => {
    const { service, http } = setup();
    const result = service.createInventoryItem(payload);
    const outcome = result.then(
      () => {
        throw new Error('Unexpected confirmation success');
      },
      (error: unknown) => error,
    );
    http
      .expectOne((r) => r.url.endsWith('/inventory/items'))
      .flush({ detail: 'Already initialized' }, { status: 409, statusText: 'Conflict' });
    expect(await outcome).toMatchObject({ status: 409 });
    http.verify();
  });
});
