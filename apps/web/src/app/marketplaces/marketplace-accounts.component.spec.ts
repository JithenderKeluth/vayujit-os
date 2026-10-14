import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { MarketplaceAccountsComponent } from './marketplace-accounts.component';

describe('MarketplaceAccountsComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MarketplaceAccountsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('renders the read-only connection center and imports through the typed service', async () => {
    const fixture = TestBed.createComponent(MarketplaceAccountsComponent);
    const http = TestBed.inject(HttpTestingController);
    const account = {
      id: 'account-1',
      marketplace: 'amazon',
      display_name: 'Local Amazon',
      seller_account_id: 'seller-1',
      environment: 'sandbox',
      enabled: false,
      credential_status: 'missing',
      validation_status: 'unknown',
      last_validated_at: null,
      capabilities: [],
      connection_state: 'AUTHORIZATION_REQUIRED',
      permission_state: 'UNVERIFIED',
      transport_mode: 'SYNTHETIC',
    };
    http.expectOne('http://127.0.0.1:8000/api/v1/marketplaces/accounts').flush([account]);
    http
      .expectOne('http://127.0.0.1:8000/api/v1/marketplaces/connectivity/capabilities')
      .flush({
        providers: [
          {
            provider: 'amazon',
            regions: ['IN'],
            transport_modes: ['SYNTHETIC'],
            supported_operations: ['catalog', 'orders', 'inventory', 'financial'],
            repo_supported: true,
            synthetic_fixture: true,
            official_contract: 'UNVERIFIED',
            sandbox: 'NOT_CONFIGURED',
            live_read_only: 'NOT_CONFIGURED',
            live_write: 'DENIED',
            external_activation_required: true,
          },
        ],
        external_writes: false,
      });
    await fixture.whenStable();
    http
      .expectOne('http://127.0.0.1:8000/api/v1/marketplaces/accounts/account-1/import-jobs')
      .flush([]);
    http
      .expectOne('http://127.0.0.1:8000/api/v1/marketplaces/accounts/account-1/reconciliation')
      .flush({
        account_id: 'account-1',
        marketplace: 'amazon',
        canonical_counts: {},
        latest_imports: {},
        last_failed_imports: {},
        freshness: {},
        imported_counts: {},
        stale_operations: [],
        exceptions: [],
        automatic_mutations: false,
        next_action: 'Review manually.',
      });
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).toContain('Read-only connectivity center');
    expect(fixture.nativeElement.textContent).toContain('AUTHORIZATION_REQUIRED');

    const component = fixture.componentInstance;
    const importPromise = component.runImport(account, 'orders');
    const importRequest = http.expectOne(
      'http://127.0.0.1:8000/api/v1/marketplaces/accounts/account-1/imports',
    );
    expect(importRequest.request.body.operation).toBe('orders');
    expect(importRequest.request.body.mode).toBe('SYNTHETIC');
    importRequest.flush({
      id: 'job-1',
      account_id: 'account-1',
      marketplace: 'amazon',
      operation: 'orders',
      mode: 'SYNTHETIC',
      status: 'SUCCEEDED',
      idempotency_key: 'ui-orders',
      correlation_id: 'corr-1',
      checkpoint_json: { complete: true },
      summary_json: {},
      provenance_json: { external_writes: false },
      pages_fetched: 1,
      records_seen: 1,
      records_imported: 1,
      records_reused: 0,
      error_code: null,
      error_message: null,
      completed_at: new Date().toISOString(),
      last_successful_sync: new Date().toISOString(),
      stale_after: new Date().toISOString(),
    });
    await fixture.whenStable();
    http
      .expectOne('http://127.0.0.1:8000/api/v1/marketplaces/accounts/account-1/reconciliation')
      .flush({
        account_id: 'account-1',
        marketplace: 'amazon',
        canonical_counts: { orders: 1 },
        latest_imports: {},
        last_failed_imports: {},
        freshness: { orders: 'FRESH' },
        imported_counts: { orders: 1 },
        stale_operations: [],
        exceptions: [],
        automatic_mutations: false,
        next_action: 'Review manually.',
      });
    await importPromise;
    await fixture.whenStable();
    expect(component.message()).toContain('orders import completed');
    http.verify();
  });
});
