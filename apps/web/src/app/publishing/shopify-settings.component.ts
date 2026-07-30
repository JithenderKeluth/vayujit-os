import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { ShopifyConnectorConfiguration, ShopifyRemoteItem } from '@vayujit/shared';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-shopify-settings',
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section class="pub-page">
      <header class="pub-header">
        <div>
          <p class="pub-eyebrow">Publishing connector</p>
          <h1>Shopify</h1>
          <p>
            Connect an owner-controlled Shopify custom app. Products remain drafts unless activation
            is explicitly permitted and selected.
          </p>
        </div>
        <a routerLink="/publishing">Back to Publishing</a>
      </header>

      @if (message()) {
        <p class="pub-notice" role="status" aria-live="polite">{{ message() }}</p>
      }
      @if (error()) {
        <p class="pub-error" role="alert">{{ error() }}</p>
      }

      <form class="pub-card pub-form" (ngSubmit)="save()">
        <label>
          Shopify store domain
          <input
            name="shopDomain"
            [(ngModel)]="form.shop_domain"
            placeholder="example-shop.myshopify.com"
            autocomplete="off"
            required
          />
          <small>Enter only the myshopify.com domain—never a full API URL.</small>
        </label>
        <label>
          Admin API access token
          <input
            name="accessToken"
            [(ngModel)]="form.access_token"
            type="password"
            autocomplete="new-password"
            [placeholder]="configuration()?.configured ? 'Leave blank to keep existing token' : ''"
          />
        </label>
        <label>
          Admin API version
          <input
            name="apiVersion"
            [(ngModel)]="form.api_version"
            pattern="20[0-9]{2}-(01|04|07|10)"
            required
          />
        </label>
        <label>
          Default product status
          <select name="status" [(ngModel)]="form.default_product_status">
            <option value="draft">Draft—recommended</option>
            <option value="active">Allow explicit activation</option>
          </select>
        </label>
        <label>
          Inventory policy
          <select name="inventory" [(ngModel)]="form.inventory_policy">
            <option value="no_inventory_write">Do not write inventory quantities</option>
            <option value="track_without_quantity">Track without quantity</option>
          </select>
        </label>
        <label>
          Variant policy
          <select name="variants" [(ngModel)]="form.variant_policy">
            <option value="default_variant">One default variant</option>
            <option value="structured_variants">Use existing structured variants</option>
          </select>
        </label>
        <label>
          Media failure policy
          <select name="media" [(ngModel)]="form.media_policy">
            <option value="fail">Fail safely</option>
            <option value="draft_without_media">Create draft without media</option>
            <option value="degraded">Create degraded recovery item</option>
          </select>
        </label>
        <label>
          Request timeout (seconds)
          <input
            name="timeout"
            [(ngModel)]="form.request_timeout_seconds"
            type="number"
            min="10"
            max="120"
          />
        </label>
        <label>
          Retry attempts
          <input
            name="retries"
            [(ngModel)]="form.max_retry_attempts"
            type="number"
            min="1"
            max="5"
          />
        </label>
        <button class="pub-button" type="submit" [disabled]="busy()">Save configuration</button>
      </form>

      @if (configuration(); as config) {
        <section class="pub-card">
          <h2>Connection state</h2>
          <dl>
            <dt>Credential</dt>
            <dd>{{ credentialLabel(config.credential_source) }}</dd>
            <dt>Validation</dt>
            <dd>
              {{ config.validation_status }} · {{ config.safe_validation_message || 'Not run' }}
            </dd>
            <dt>Connector</dt>
            <dd>{{ config.enabled ? 'Enabled' : 'Disabled' }}</dd>
            <dt>Store</dt>
            <dd>{{ config.shop_domain || 'Not configured' }}</dd>
            <dt>API version</dt>
            <dd>{{ config.api_version }}</dd>
          </dl>
          <div class="pub-actions">
            <button type="button" (click)="validate()" [disabled]="busy()">Validate</button>
            <button
              type="button"
              (click)="toggle(config.enabled ? 'disable' : 'enable')"
              [disabled]="busy()"
            >
              {{ config.enabled ? 'Disable' : 'Enable' }}
            </button>
            <button type="button" (click)="removeCredential()" [disabled]="busy()">
              Remove stored token
            </button>
          </div>
        </section>

        <section class="pub-card">
          <header class="pub-header">
            <div>
              <h2>Remote discovery</h2>
              <p>Results are bounded and cached for 15 minutes.</p>
            </div>
            <button type="button" (click)="discover(true)" [disabled]="busy() || !config.enabled">
              Refresh
            </button>
          </header>
          <label>
            Search collections
            <input
              [(ngModel)]="collectionSearch"
              (ngModelChange)="discover(false)"
              [ngModelOptions]="{ standalone: true }"
            />
          </label>
          <div class="pub-grid">
            <div>
              <h3>Collections</h3>
              @for (item of collections(); track item.id) {
                <p>
                  {{ item.name }} <small>{{ item.handle || '' }}</small>
                </p>
              } @empty {
                <p>No collections loaded.</p>
              }
            </div>
            <div>
              <h3>Publications</h3>
              @for (item of publications(); track item.id) {
                <p>{{ item.name }}</p>
              } @empty {
                <p>Publication discovery may be unavailable for this app.</p>
              }
            </div>
          </div>
        </section>
      }
    </section>
  `,
  styleUrl: './publishing.css',
})
export class ShopifySettingsComponent implements OnInit {
  private readonly api = inject(PublishingService);
  readonly configuration = signal<ShopifyConnectorConfiguration | null>(null);
  readonly collections = signal<ShopifyRemoteItem[]>([]);
  readonly publications = signal<ShopifyRemoteItem[]>([]);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  collectionSearch = '';
  form = {
    shop_domain: '',
    access_token: '',
    api_version: '2026-07',
    default_product_status: 'draft' as 'draft' | 'active',
    default_publication_ids: [] as string[],
    inventory_policy: 'no_inventory_write' as 'no_inventory_write' | 'track_without_quantity',
    variant_policy: 'default_variant' as 'default_variant' | 'structured_variants',
    media_policy: 'fail' as 'fail' | 'draft_without_media' | 'degraded',
    request_timeout_seconds: 45,
    max_retry_attempts: 3,
  };

  ngOnInit(): void {
    void this.load();
  }

  credentialLabel(source: ShopifyConnectorConfiguration['credential_source']) {
    return {
      application: 'Configured in application',
      deployment: 'Configured by deployment',
      not_configured: 'Not configured',
    }[source];
  }

  private async load() {
    try {
      const value = await this.api.shopifyConfiguration();
      this.configuration.set(value);
      this.form.shop_domain = value.shop_domain;
      this.form.api_version = value.api_version;
      this.form.default_product_status = value.default_product_status;
      this.form.default_publication_ids = value.default_publication_ids;
      this.form.inventory_policy = value.inventory_policy;
      this.form.variant_policy = value.variant_policy;
      this.form.media_policy = value.media_policy;
      this.form.request_timeout_seconds = value.request_timeout_seconds;
      this.form.max_retry_attempts = value.max_retry_attempts;
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    }
  }

  async save() {
    await this.run(async () => {
      const payload = { ...this.form };
      if (!payload.access_token) delete (payload as { access_token?: string }).access_token;
      this.configuration.set(await this.api.saveShopifyConfiguration(payload));
      this.form.access_token = '';
      this.message.set('Shopify configuration saved. Validate it before enabling.');
    });
  }

  async validate() {
    await this.run(async () => {
      const result = await this.api.validateShopify();
      await this.load();
      this.message.set(result.safe_message);
    });
  }

  async toggle(action: 'enable' | 'disable') {
    await this.run(async () => {
      this.configuration.set(await this.api.setShopifyEnabled(action));
      this.message.set(`Shopify ${action}d.`);
    });
  }

  async removeCredential() {
    if (!confirm('Remove the stored Shopify Admin API token and disable the connector?')) return;
    await this.run(async () => {
      this.configuration.set(await this.api.removeShopifyCredential());
      this.message.set('Shopify credential removed.');
    });
  }

  async discover(refresh: boolean) {
    const config = this.configuration();
    if (!config?.enabled) return;
    await this.run(async () => {
      const [collections, publications] = await Promise.all([
        this.api.shopifyDiscovery('collections', this.collectionSearch, refresh),
        this.api.shopifyDiscovery('publications', '', refresh),
      ]);
      this.collections.set(collections.items);
      this.publications.set(publications.items);
      if (collections.stale || publications.stale)
        this.message.set('Showing stale cached discovery results.');
    });
  }

  private async run(operation: () => Promise<void>) {
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    try {
      await operation();
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}
