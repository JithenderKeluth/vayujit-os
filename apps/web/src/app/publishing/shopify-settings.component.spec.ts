import { provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { ShopifySettingsComponent } from './shopify-settings.component';
import { PublishingService } from './publishing.service';

describe('ShopifySettingsComponent', () => {
  const configuration = {
    connector_key: 'shopify' as const,
    display_name: 'Shopify',
    configured: true,
    credential_source: 'application' as const,
    shop_domain: 'test-shop.myshopify.com',
    api_version: '2026-07',
    enabled: false,
    default_product_status: 'draft' as const,
    default_publication_ids: [],
    inventory_policy: 'no_inventory_write' as const,
    variant_policy: 'default_variant' as const,
    media_policy: 'fail' as const,
    request_timeout_seconds: 45,
    max_retry_attempts: 3,
    validation_status: 'valid',
    safe_validation_message: 'Valid',
    last_validated_at: null,
    last_validation_latency_ms: 20,
    capabilities: {},
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        {
          provide: PublishingService,
          useValue: {
            shopifyConfiguration: () => Promise.resolve(configuration),
            saveShopifyConfiguration: () => Promise.resolve(configuration),
            validateShopify: () => Promise.resolve({ safe_message: 'Valid' }),
            setShopifyEnabled: () => Promise.resolve(configuration),
            removeShopifyCredential: () => Promise.resolve(configuration),
            shopifyDiscovery: () =>
              Promise.resolve({
                items: [],
                has_more: false,
                end_cursor: null,
                cached: false,
                stale: false,
              }),
          },
        },
      ],
    });
  });

  it('never renders the stored access token', async () => {
    const fixture = TestBed.createComponent(ShopifySettingsComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Configured in application');
    expect(fixture.nativeElement.textContent).not.toContain('secret-token');
    const token = fixture.nativeElement.querySelector(
      'input[name=accessToken]',
    ) as HTMLInputElement;
    expect(token.type).toBe('password');
    expect(token.value).toBe('');
  });

  it('defaults to draft and no inventory writes', () => {
    const component = TestBed.createComponent(ShopifySettingsComponent).componentInstance;
    expect(component.form.default_product_status).toBe('draft');
    expect(component.form.inventory_policy).toBe('no_inventory_write');
  });
});
