import { HttpClient } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

interface AmazonAccount {
  id: string;
  display_name: string;
  seller_account_id: string;
  enabled: boolean;
  credential_status: string;
  validation_status: string;
  last_validated_at: string | null;
  marketplace_id: string;
  currency: string;
}
interface AmazonAttribute {
  key: string;
  label: string;
  type: string;
  required: boolean;
  options?: string[];
}
interface AmazonVariant {
  stable_variant_key: string;
  sku: string;
  variation_theme: string;
  options: Record<string, string>;
  barcode: string;
  price: number | null;
  compare_at_price: number | null;
  currency: string;
  listing_state?: string;
}
interface AmazonMedia {
  media_id: string;
  position: number;
  alt_text: string;
  status?: string;
  mime_type?: string;
  width?: number;
  height?: number;
  checksum_sha256?: string;
}
interface AmazonReadiness {
  ready: boolean;
  blocking: Array<{ code: string; message: string; field?: string }>;
  warnings: Array<{ code: string; message: string }>;
  informational: Array<{ code: string; message: string }>;
  artifact_version: number | null;
}
interface AmazonOrder {
  amazon_order_id: string;
  purchase_date: string;
  status: string;
  raw_status: string;
  payment_status: string;
  fulfilment_status: string;
  totals: Record<string, string>;
  tax: string;
  shipping: string;
  discount: string;
  items: Array<{ sku: string; title: string; quantity: number; unit_price: string; total: string }>;
  fulfilments: Array<{ status: string; carrier?: string; tracking_reference?: string }>;
}
interface AmazonSettlement {
  settlement_id: string;
  period_start: string;
  period_end: string;
  status: string;
  currency: string;
  gross_sales: string;
  fees: string;
  refunds: string;
  withholding: string;
  net: string;
  lines: Array<{ line_type: string; amount: string; currency: string; description: string }>;
}
interface AmazonReturn {
  reference: string;
  order_id: string;
  status: string;
  reason: string;
  quantity: number;
  refund_amount: string;
  safe_notes: string;
  refunds: Array<{ amount: string; currency: string; status: string; reason: string }>;
}
interface AmazonDrift {
  drift_state: string;
  classification: string;
  fields: Array<{ path: string; local: unknown; remote: unknown; classification: string }>;
}
interface AmazonProfitability {
  gross_sales: string;
  refunds: string;
  fees: string;
  contribution: string;
  estimated_profit: string | null;
  profit_status: string;
  missing_inputs: string[];
  accounting_semantics: string;
}

@Component({
  selector: 'app-amazon-workspace',
  imports: [FormsModule],
  template: `
    <section class="marketplace-page">
      <header>
        <h1>Amazon Marketplace workspace</h1>
        <p>
          Prepare, review, and operate a fake-certified Amazon listing without exposing secrets.
        </p>
      </header>
      @if (message()) {
        <p class="marketplace-success" role="status">{{ message() }}</p>
      }
      @if (error()) {
        <p class="marketplace-error" role="alert">{{ error() }}</p>
      }

      <section class="marketplace-card">
        <h2>Account and connector health</h2>
        <form class="marketplace-form" (ngSubmit)="configure()">
          <label for="amazon-display-name"
            >Display name<input
              id="amazon-display-name"
              name="displayName"
              [(ngModel)]="displayName"
              required
          /></label>
          <label for="amazon-seller-id"
            >Seller account ID<input
              id="amazon-seller-id"
              name="sellerId"
              [(ngModel)]="sellerId"
              required
          /></label>
          <label for="amazon-credential"
            >Credential (write only)<input
              id="amazon-credential"
              type="password"
              name="credential"
              [(ngModel)]="credential"
              autocomplete="new-password"
          /></label>
          <button type="submit">Configure account</button>
        </form>
        @if (account(); as current) {
          <div class="marketplace-status-row">
            <strong>{{ current.display_name }}</strong
            ><span>{{ current.marketplace_id }} · {{ current.currency }}</span
            ><span>{{ current.credential_status }} / {{ current.validation_status }}</span>
          </div>
          <p class="muted">Last validated: {{ current.last_validated_at || 'Not validated' }}</p>
          <button type="button" (click)="validate()">Validate</button>
          <button type="button" (click)="toggle()">
            {{ current.enabled ? 'Disable' : 'Enable' }}
          </button>
          <button type="button" (click)="replaceCredential()">Replace credential</button>
          <button type="button" (click)="removeCredential()">Remove credential</button>
          <button type="button" (click)="loadDiagnostics()">Refresh diagnostics</button>
        }
        @if (diagnostics(); as diag) {
          <dl class="marketplace-stats">
            <div>
              <dt>Listings</dt>
              <dd>{{ diagValue(diag, 'listing_count') }}</dd>
            </div>
            <div>
              <dt>Remote validation</dt>
              <dd>{{ diagValue(diag, 'real_amazon_validation') }}</dd>
            </div>
            <div>
              <dt>Recent retries</dt>
              <dd>{{ diagValue(diag, 'recent_retry_count') }}</dd>
            </div>
          </dl>
        }
      </section>

      <section class="marketplace-card">
        <h2>Listing editor</h2>
        <p class="muted">
          Listing ID: {{ listingId || 'Select a listing route to enable mutations.' }}
        </p>
        <div class="marketplace-grid">
          <label for="amazon-product-type"
            >Product type<select
              id="amazon-product-type"
              name="productType"
              [(ngModel)]="productType"
              (change)="loadAttributes()"
            >
              <option value="PRODUCT">PRODUCT</option>
              <option value="HOME">HOME</option>
              <option value="APPAREL">APPAREL</option>
            </select></label
          >
          <label for="amazon-title"
            >Title<input id="amazon-title" name="title" [(ngModel)]="title"
          /></label>
          <label for="amazon-list-price"
            >List price<input
              id="amazon-list-price"
              type="number"
              name="listPrice"
              [(ngModel)]="listPrice"
              min="0"
          /></label>
          <label for="amazon-selling-price"
            >Selling price<input
              id="amazon-selling-price"
              type="number"
              name="sellingPrice"
              [(ngModel)]="sellingPrice"
              min="0"
          /></label>
          <label for="amazon-quantity"
            >Inventory target<input
              id="amazon-quantity"
              type="number"
              name="quantity"
              [(ngModel)]="quantity"
              min="0"
          /></label>
        </div>
        @for (field of attributes(); track field.key) {
          <label class="field-label" [for]="'amazon-attribute-' + field.key"
            >{{ field.label }}
            @if (field.required) {
              <span aria-hidden="true">*</span>
            }
            <input
              [id]="'amazon-attribute-' + field.key"
              [name]="field.key"
              [(ngModel)]="attributeValues[field.key]"
          /></label>
        }
        <div class="marketplace-actions">
          <button type="button" (click)="preview()">Preview readiness</button
          ><button type="button" (click)="submitListing()">Submit approved listing</button
          ><button type="button" (click)="reconcileListing()">Reconcile remote status</button
          ><button type="button" (click)="submitPrice()">Confirm price update</button
          ><button type="button" (click)="updateInventory()">Confirm inventory update</button>
        </div>
      </section>

      @if (readiness(); as ready) {
        <section class="marketplace-card" aria-labelledby="readiness-heading">
          <h2 id="readiness-heading">
            Server-driven readiness
            <span class="marketplace-status">{{ ready.ready ? 'Ready' : 'Blocked' }}</span>
          </h2>
          <p>Exact approved Artifact version: {{ ready.artifact_version ?? 'none' }}</p>
          <div class="readiness-grid">
            <div>
              <h3>Blocking</h3>
              <ul>
                @for (item of ready.blocking; track item.code) {
                  <li>{{ item.message }}</li>
                } @empty {
                  <li>None</li>
                }
              </ul>
            </div>
            <div>
              <h3>Warnings</h3>
              <ul>
                @for (item of ready.warnings; track item.code) {
                  <li>{{ item.message }}</li>
                } @empty {
                  <li>None</li>
                }
              </ul>
            </div>
            <div>
              <h3>Informational</h3>
              <ul>
                @for (item of ready.informational; track item.code) {
                  <li>{{ item.message }}</li>
                } @empty {
                  <li>None</li>
                }
              </ul>
            </div>
          </div>
        </section>
      }

      <section class="marketplace-card">
        <h2>Variant editor and option matrix</h2>
        <div class="marketplace-form">
          <label for="amazon-matrix"
            >Matrix dimensions<input
              id="amazon-matrix"
              name="matrix"
              [(ngModel)]="matrixDimensionsText"
              placeholder="Color=Red|Blue; Size=S|M" /></label
          ><button type="button" (click)="buildVariantMatrix()">Build matrix</button
          ><button type="button" (click)="addVariant()">Add variant</button
          ><button type="button" (click)="saveVariants()">Save variants</button>
        </div>
        <div class="marketplace-table">
          <table>
            <caption>
              Stable variant combinations
            </caption>
            <thead>
              <tr>
                <th scope="col">Key</th>
                <th scope="col">Options</th>
                <th scope="col">SKU</th>
                <th scope="col">Theme</th>
                <th scope="col">Price</th>
                <th scope="col">Barcode</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              @for (variant of variants(); track variant.stable_variant_key; let index = $index) {
                <tr>
                  <td>
                    <input
                      [id]="'variant-key-' + index"
                      [name]="'variant-key-' + index"
                      [(ngModel)]="variant.stable_variant_key"
                    />
                  </td>
                  <td>{{ formatJson(variant.options) }}</td>
                  <td>
                    <input
                      [id]="'variant-sku-' + index"
                      [name]="'variant-sku-' + index"
                      [(ngModel)]="variant.sku"
                    />
                  </td>
                  <td>
                    <input
                      [id]="'variant-theme-' + index"
                      [name]="'variant-theme-' + index"
                      [(ngModel)]="variant.variation_theme"
                    />
                  </td>
                  <td>
                    <input
                      [id]="'variant-price-' + index"
                      type="number"
                      [name]="'variant-price-' + index"
                      [(ngModel)]="variant.price"
                      min="0"
                    />
                  </td>
                  <td>
                    <input
                      [id]="'variant-barcode-' + index"
                      [name]="'variant-barcode-' + index"
                      [(ngModel)]="variant.barcode"
                    />
                  </td>
                  <td>
                    <button type="button" (click)="duplicateVariant(index)">Duplicate</button
                    ><button type="button" (click)="removeVariant(index)">Remove</button>
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="7">No variants yet.</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>

      <section class="marketplace-card">
        <h2>Media editor</h2>
        <div class="marketplace-form">
          <label for="amazon-media-id"
            >Media Asset ID<input
              id="amazon-media-id"
              name="mediaId"
              [(ngModel)]="newMediaId" /></label
          ><label for="amazon-media-alt"
            >Alt text<input
              id="amazon-media-alt"
              name="mediaAlt"
              [(ngModel)]="newMediaAlt" /></label
          ><button type="button" (click)="addMedia()">Add media</button
          ><button type="button" (click)="saveMedia()">Save ordered media</button>
        </div>
        <div class="marketplace-table">
          <table>
            <caption>
              Ordered gallery
            </caption>
            <thead>
              <tr>
                <th scope="col">Position</th>
                <th scope="col">Asset</th>
                <th scope="col">Alt text</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              @for (item of media(); track item.media_id; let index = $index) {
                <tr>
                  <td>
                    {{ item.position }}
                    @if (index === 0) {
                      <span aria-label="Main image">(main)</span>
                    }
                  </td>
                  <td>{{ item.media_id }}</td>
                  <td>
                    <input
                      [id]="'media-alt-' + index"
                      [name]="'media-alt-' + index"
                      [(ngModel)]="item.alt_text"
                    />
                  </td>
                  <td>{{ item.status || 'local' }}</td>
                  <td>
                    <button type="button" (click)="moveMedia(index, -1)" [disabled]="index === 0">
                      Move up</button
                    ><button
                      type="button"
                      (click)="moveMedia(index, 1)"
                      [disabled]="index === media().length - 1"
                    >
                      Move down</button
                    ><button type="button" (click)="removeMedia(index)">Remove</button>
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="5">No media mappings yet.</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>

      <section class="marketplace-card">
        <h2>Orders and fulfilment</h2>
        <button type="button" (click)="importOrders()">Import orders</button>
        <div class="marketplace-table">
          <table>
            <caption>
              Normalized orders
            </caption>
            <thead>
              <tr>
                <th scope="col">Order</th>
                <th scope="col">Status</th>
                <th scope="col">Payment</th>
                <th scope="col">Fulfilment</th>
                <th scope="col">Items</th>
                <th scope="col">Totals</th>
              </tr>
            </thead>
            <tbody>
              @for (order of orders(); track order.amazon_order_id) {
                <tr>
                  <td>
                    {{ order.amazon_order_id }}<br /><small>{{ order.purchase_date }}</small>
                  </td>
                  <td>
                    {{ order.status }}<br /><small>{{ order.raw_status }}</small>
                  </td>
                  <td>{{ order.payment_status }}</td>
                  <td>
                    {{ order.fulfilment_status }}
                    <ul>
                      @for (fulfilment of order.fulfilments; track fulfilment.tracking_reference) {
                        <li>
                          {{ fulfilment.carrier || 'Carrier pending' }}
                          {{ fulfilment.tracking_reference || '' }}
                        </li>
                      }
                    </ul>
                  </td>
                  <td>
                    @for (item of order.items; track item.sku) {
                      <div>{{ item.sku }} × {{ item.quantity }} — {{ item.total }}</div>
                    }
                  </td>
                  <td>
                    {{ formatJson(order.totals) }}<br />Tax {{ order.tax }} · Shipping
                    {{ order.shipping }}
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="6">No orders imported.</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>

      <section class="marketplace-card">
        <h2>Returns and refunds</h2>
        <button type="button" (click)="importReturns()">Import return records</button>
        <div class="marketplace-table">
          <table>
            <caption>
              Read-only returns and refunds
            </caption>
            <thead>
              <tr>
                <th scope="col">Reference</th>
                <th scope="col">Order</th>
                <th scope="col">Status</th>
                <th scope="col">Reason</th>
                <th scope="col">Refund</th>
                <th scope="col">Safe notes</th>
              </tr>
            </thead>
            <tbody>
              @for (item of returns(); track item.reference) {
                <tr>
                  <td>{{ item.reference }}</td>
                  <td>{{ item.order_id }}</td>
                  <td>{{ item.status }}</td>
                  <td>{{ item.reason }} (×{{ item.quantity }})</td>
                  <td>
                    {{ item.refund_amount }}
                    <ul>
                      @for (refund of item.refunds; track refund.reason) {
                        <li>{{ refund.amount }} {{ refund.currency }} · {{ refund.status }}</li>
                      }
                    </ul>
                  </td>
                  <td>{{ item.safe_notes }}</td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="6">No return records imported.</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </section>

      <section class="marketplace-card">
        <h2>Settlement and profitability</h2>
        <button type="button" (click)="importFinancials()">Import settlements and fees</button>
        <div class="marketplace-table">
          <table>
            <caption>
              Settlement periods
            </caption>
            <thead>
              <tr>
                <th scope="col">Settlement</th>
                <th scope="col">Period</th>
                <th scope="col">Gross</th>
                <th scope="col">Fees</th>
                <th scope="col">Refunds</th>
                <th scope="col">Net</th>
              </tr>
            </thead>
            <tbody>
              @for (settlement of settlements(); track settlement.settlement_id) {
                <tr>
                  <td>{{ settlement.settlement_id }}<br />{{ settlement.status }}</td>
                  <td>{{ settlement.period_start }} – {{ settlement.period_end }}</td>
                  <td>{{ settlement.gross_sales }} {{ settlement.currency }}</td>
                  <td>{{ settlement.fees }}</td>
                  <td>{{ settlement.refunds }}</td>
                  <td>
                    {{ settlement.net }}
                    <details>
                      <summary>Lines</summary>
                      @for (line of settlement.lines; track line.description) {
                        <div>{{ line.line_type }}: {{ line.amount }} {{ line.currency }}</div>
                      }
                    </details>
                  </td>
                </tr>
              } @empty {
                <tr>
                  <td colspan="6">No settlements imported.</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        @if (profitability(); as profit) {
          <div class="marketplace-callout">
            <strong>Profitability: {{ profit.profit_status }}</strong>
            <p>
              Gross {{ profit.gross_sales }} · Fees {{ profit.fees }} · Refunds
              {{ profit.refunds }} · Contribution {{ profit.contribution }}
            </p>
            <p>{{ profit.accounting_semantics }}</p>
            <p>Missing inputs: {{ profit.missing_inputs.join(', ') || 'none' }}</p>
          </div>
        }
      </section>

      <section class="marketplace-card">
        <h2>Drift matrix and guarded overwrite</h2>
        <div class="marketplace-actions">
          <button type="button" (click)="loadDrift()">Review drift</button
          ><button type="button" (click)="keepRemote()">Keep remote</button
          ><button type="button" (click)="overwriteDrift()">Overwrite remote (confirm)</button>
        </div>
        @if (drift(); as currentDrift) {
          <p>
            State: {{ currentDrift.drift_state }} · Classification:
            {{ currentDrift.classification }}
          </p>
          <div class="marketplace-table">
            <table>
              <caption>
                Local versus remote
              </caption>
              <thead>
                <tr>
                  <th scope="col">Field</th>
                  <th scope="col">Local</th>
                  <th scope="col">Remote</th>
                  <th scope="col">Class</th>
                </tr>
              </thead>
              <tbody>
                @for (field of currentDrift.fields; track field.path) {
                  <tr>
                    <td>{{ field.path }}</td>
                    <td>{{ formatJson(field.local) }}</td>
                    <td>{{ formatJson(field.remote) }}</td>
                    <td>{{ field.classification }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>

      <p class="muted">
        This workspace is fake-certified for local development. Real Amazon validation and remote
        mutations are not performed without operator-controlled credentials.
      </p>
    </section>
  `,
  styleUrl: './marketplaces.css',
})
export class AmazonWorkspaceComponent {
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly baseUrl = environment.apiUrl + '/marketplaces/amazon';
  readonly listingId = this.route.snapshot.paramMap.get('id');
  readonly account = signal<AmazonAccount | null>(null);
  readonly attributes = signal<AmazonAttribute[]>([]);
  readonly variants = signal<AmazonVariant[]>([]);
  readonly media = signal<AmazonMedia[]>([]);
  readonly readiness = signal<AmazonReadiness | null>(null);
  readonly orders = signal<AmazonOrder[]>([]);
  readonly settlements = signal<AmazonSettlement[]>([]);
  readonly returns = signal<AmazonReturn[]>([]);
  readonly profitability = signal<AmazonProfitability | null>(null);
  readonly drift = signal<AmazonDrift | null>(null);
  readonly diagnostics = signal<Record<string, unknown> | null>(null);
  readonly message = signal('');
  readonly error = signal('');
  readonly attributeValues: Record<string, string> = {};
  displayName = '';
  sellerId = '';
  credential = '';
  productType = 'PRODUCT';
  title = '';
  listPrice = 0;
  sellingPrice = 0;
  quantity = 0;
  matrixDimensionsText = '';
  newMediaId = '';
  newMediaAlt = '';
  private readonly options = { withCredentials: true } as const;

  constructor() {
    void this.loadAccount();
  }

  formatJson(value: unknown): string {
    return typeof value === 'string' ? value : JSON.stringify(value);
  }
  diagValue(value: Record<string, unknown>, key: string): unknown {
    return value[key];
  }
  private clearStatus(): void {
    this.message.set('');
    this.error.set('');
  }
  private async request<T>(
    call: () => import('rxjs').Observable<T>,
    success?: string,
  ): Promise<T | null> {
    try {
      const value = await firstValueFrom(call());
      if (success) this.message.set(success);
      this.error.set('');
      return value;
    } catch {
      this.error.set('The Amazon operation was rejected safely.');
      return null;
    }
  }

  async loadAccount(): Promise<void> {
    const accounts = await this.request(() =>
      this.http.get<AmazonAccount[]>(this.baseUrl + '/accounts', this.options),
    );
    if (!accounts) return;
    this.account.set(accounts[0] || null);
    if (!accounts[0]) return;
    this.displayName = accounts[0].display_name;
    this.sellerId = accounts[0].seller_account_id;
    await this.loadAttributes();
    await Promise.all([this.loadDiagnostics(), this.loadListingData()]);
  }
  async configure(): Promise<void> {
    const value = await this.request(
      () =>
        this.http.post<AmazonAccount>(
          this.baseUrl + '/accounts',
          {
            display_name: this.displayName,
            seller_account_id: this.sellerId,
            credentials: this.credential ? { token: this.credential } : {},
          },
          this.options,
        ),
      'Amazon account configured.',
    );
    if (value) {
      this.account.set(value);
      this.credential = '';
    }
  }
  async validate(): Promise<void> {
    await this.accountAction('validate', {}, 'Amazon account validated.');
  }
  async toggle(): Promise<void> {
    const current = this.account();
    if (current)
      await this.accountAction(
        current.enabled ? 'disable' : 'enable',
        { confirm: true },
        'Amazon account state updated.',
      );
  }
  async replaceCredential(): Promise<void> {
    if (!this.account() || !this.credential) {
      this.error.set('Enter a replacement credential first.');
      return;
    }
    await this.accountAction(
      'credentials',
      { credentials: { token: this.credential } },
      'Amazon credential replaced.',
    );
    this.credential = '';
  }
  async removeCredential(): Promise<void> {
    await this.accountAction(
      'credentials',
      { confirm: true },
      'Amazon credential removed.',
      'DELETE',
    );
  }
  private async accountAction(
    action: string,
    body: Record<string, unknown>,
    success: string,
    method: 'POST' | 'DELETE' = 'POST',
  ): Promise<void> {
    const current = this.account();
    if (!current) return;
    const call =
      method === 'DELETE'
        ? () =>
            this.http.delete<AmazonAccount>(
              this.baseUrl + '/accounts/' + current.id + '/credentials',
              { ...this.options, body },
            )
        : () =>
            this.http.post<AmazonAccount>(
              this.baseUrl + '/accounts/' + current.id + '/' + action,
              body,
              this.options,
            );
    const value = await this.request(call, success);
    if (value) this.account.set(value);
  }
  async loadAttributes(): Promise<void> {
    const current = this.account();
    if (!current) return;
    const response = await this.request<{ attributes: AmazonAttribute[] }>(() =>
      this.http.get<{ attributes: AmazonAttribute[] }>(
        this.baseUrl +
          '/accounts/' +
          current.id +
          '/product-types/' +
          this.productType +
          '/attributes',
        this.options,
      ),
    );
    if (response) this.attributes.set(response.attributes);
  }
  private async loadListingData(): Promise<void> {
    if (!this.listingId) return;
    await Promise.all([
      this.loadReadiness(),
      this.loadVariants(),
      this.loadMedia(),
      this.loadDrift(),
    ]);
  }
  async loadReadiness(): Promise<void> {
    if (this.listingId) {
      const value = await this.request<AmazonReadiness>(() =>
        this.http.get<AmazonReadiness>(
          this.baseUrl + '/listings/' + this.listingId + '/readiness',
          this.options,
        ),
      );
      if (value) this.readiness.set(value);
    }
  }
  async loadVariants(): Promise<void> {
    if (this.listingId) {
      const value = await this.request<AmazonVariant[]>(() =>
        this.http.get<AmazonVariant[]>(
          this.baseUrl + '/listings/' + this.listingId + '/variants',
          this.options,
        ),
      );
      if (value) this.variants.set(value);
    }
  }
  async loadMedia(): Promise<void> {
    if (this.listingId) {
      const value = await this.request<AmazonMedia[]>(() =>
        this.http.get<AmazonMedia[]>(
          this.baseUrl + '/listings/' + this.listingId + '/media',
          this.options,
        ),
      );
      if (value) this.media.set(value);
    }
  }
  async loadDiagnostics(): Promise<void> {
    const current = this.account();
    if (current) {
      const value = await this.request<Record<string, unknown>>(() =>
        this.http.get<Record<string, unknown>>(
          this.baseUrl + '/accounts/' + current.id + '/diagnostics',
          this.options,
        ),
      );
      if (value) this.diagnostics.set(value);
    }
  }
  async preview(): Promise<void> {
    if (!this.listingId) return;
    await this.request(
      () =>
        this.http.post(
          this.baseUrl + '/listings/' + this.listingId + '/preview',
          {
            product_type: this.productType,
            attributes: this.attributeValues,
            media_count: this.media().length,
          },
          this.options,
        ),
      'Readiness preview captured.',
    );
    await this.loadReadiness();
  }
  async submitListing(): Promise<void> {
    if (!this.listingId) return;
    await this.request(
      () =>
        this.http.post(
          this.baseUrl + '/listings/' + this.listingId + '/submit',
          {
            product_type: this.productType,
            attributes: this.attributeValues,
            idempotency_key: 'amazon-ui-submit-' + this.listingId,
          },
          this.options,
        ),
      'Amazon listing submission recorded.',
    );
  }
  async reconcileListing(): Promise<void> {
    if (this.listingId)
      await this.request(
        () =>
          this.http.post(
            this.baseUrl + '/listings/' + this.listingId + '/reconcile',
            {},
            this.options,
          ),
        'Remote listing reconciled.',
      );
  }
  async submitPrice(): Promise<void> {
    if (!this.listingId || !window.confirm('Confirm this price update?')) return;
    await this.request(
      () =>
        this.http.post(
          this.baseUrl + '/listings/' + this.listingId + '/pricing',
          {
            list_price: this.listPrice,
            selling_price: this.sellingPrice,
            currency: this.account()?.currency || 'INR',
            confirm: true,
            idempotency_key: 'amazon-ui-price-' + Date.now(),
          },
          this.options,
        ),
      'Price update recorded.',
    );
  }
  async updateInventory(): Promise<void> {
    if (!this.listingId || !window.confirm('Confirm this explicit inventory update?')) return;
    await this.request(
      () =>
        this.http.post(
          this.baseUrl + '/listings/' + this.listingId + '/inventory',
          {
            quantity: this.quantity,
            confirm: true,
            idempotency_key: 'amazon-ui-inventory-' + Date.now(),
          },
          this.options,
        ),
      'Inventory update recorded.',
    );
  }
  addVariant(): void {
    const rows = [
      ...this.variants(),
      {
        stable_variant_key: 'variant-' + (this.variants().length + 1),
        sku: '',
        variation_theme: 'Color',
        options: {},
        barcode: '',
        price: this.sellingPrice || null,
        compare_at_price: this.listPrice || null,
        currency: this.account()?.currency || 'INR',
      },
    ];
    this.variants.set(rows);
  }
  removeVariant(index: number): void {
    this.variants.set(this.variants().filter((_, rowIndex) => rowIndex !== index));
  }
  duplicateVariant(index: number): void {
    const source = this.variants()[index];
    if (!source) return;
    this.variants.set([
      ...this.variants(),
      {
        ...source,
        stable_variant_key: source.stable_variant_key + '-copy',
        sku: source.sku ? source.sku + '-COPY' : '',
      },
    ]);
  }
  buildVariantMatrix(): void {
    const dimensions = this.matrixDimensionsText
      .split(';')
      .map((entry) => entry.trim())
      .filter(Boolean)
      .map((entry) => {
        const [name, values] = entry.split('=');
        return {
          name: name.trim(),
          values: (values || '')
            .split('|')
            .map((value) => value.trim())
            .filter(Boolean),
        };
      })
      .filter((entry) => entry.name && entry.values.length);
    const combinations: Array<Record<string, string>> = [{}];
    for (const dimension of dimensions) {
      const next: Array<Record<string, string>> = [];
      for (const current of combinations)
        for (const value of dimension.values) next.push({ ...current, [dimension.name]: value });
      if (next.length > 100) {
        this.error.set('Variant matrix is limited to 100 combinations.');
        return;
      }
      combinations.splice(0, combinations.length, ...next);
    }
    const existing = new Map(
      this.variants().map((variant) => [this.combinationKey(variant.options), variant]),
    );
    this.variants.set(
      combinations.map(
        (options, index) =>
          existing.get(this.combinationKey(options)) || {
            stable_variant_key: 'matrix-' + (index + 1),
            sku: '',
            variation_theme: dimensions.map((dimension) => dimension.name).join('-'),
            options,
            barcode: '',
            price: this.sellingPrice || null,
            compare_at_price: this.listPrice || null,
            currency: this.account()?.currency || 'INR',
          },
      ),
    );
    this.message.set('Variant matrix generated without losing equivalent existing rows.');
  }
  private combinationKey(options: Record<string, string>): string {
    return Object.keys(options)
      .sort()
      .map((key) => key + '=' + options[key])
      .join('|');
  }
  async saveVariants(): Promise<void> {
    if (!this.listingId) return;
    await this.request(
      () =>
        this.http.post(
          this.baseUrl + '/listings/' + this.listingId + '/variants',
          { variants: this.variants(), idempotency_key: 'amazon-ui-variants-' + Date.now() },
          this.options,
        ),
      'Variants saved.',
    );
    await this.loadReadiness();
  }
  addMedia(): void {
    if (!this.newMediaId.trim()) {
      this.error.set('Enter a Media Asset ID first.');
      return;
    }
    this.media.set([
      ...this.media(),
      {
        media_id: this.newMediaId.trim(),
        position: this.media().length,
        alt_text: this.newMediaAlt.trim(),
      },
    ]);
    this.newMediaId = '';
    this.newMediaAlt = '';
  }
  removeMedia(index: number): void {
    this.media.set(
      this.media()
        .filter((_, rowIndex) => rowIndex !== index)
        .map((item, position) => ({ ...item, position })),
    );
  }
  moveMedia(index: number, delta: number): void {
    const target = index + delta;
    const rows = [...this.media()];
    if (target < 0 || target >= rows.length) return;
    [rows[index], rows[target]] = [rows[target], rows[index]];
    this.media.set(rows.map((item, position) => ({ ...item, position })));
  }
  async saveMedia(): Promise<void> {
    if (!this.listingId) return;
    await this.request(
      () =>
        this.http.post(
          this.baseUrl + '/listings/' + this.listingId + '/media',
          {
            media: this.media().map((item) => ({
              media_id: item.media_id,
              position: item.position,
              alt_text: item.alt_text,
            })),
            idempotency_key: 'amazon-ui-media-' + Date.now(),
          },
          this.options,
        ),
      'Media ordering saved.',
    );
    await this.loadReadiness();
  }
  async importOrders(): Promise<void> {
    const current = this.account();
    if (!current) return;
    await this.request(
      () =>
        this.http.post(
          this.baseUrl + '/accounts/' + current.id + '/orders/import',
          {},
          this.options,
        ),
      'Orders imported.',
    );
    const value = await this.request<AmazonOrder[]>(() =>
      this.http.get<AmazonOrder[]>(
        this.baseUrl + '/accounts/' + current.id + '/orders',
        this.options,
      ),
    );
    if (value) this.orders.set(value);
  }
  async importFinancials(): Promise<void> {
    const current = this.account();
    if (!current) return;
    await this.request(
      () =>
        this.http.post(
          this.baseUrl + '/accounts/' + current.id + '/financial-events/import',
          {},
          this.options,
        ),
      'Settlements and fees imported.',
    );
    const value = await this.request<AmazonSettlement[]>(() =>
      this.http.get<AmazonSettlement[]>(
        this.baseUrl + '/accounts/' + current.id + '/settlements',
        this.options,
      ),
    );
    if (value) this.settlements.set(value);
    const profit = await this.request<AmazonProfitability>(() =>
      this.http.get<AmazonProfitability>(
        this.baseUrl + '/accounts/' + current.id + '/profitability',
        this.options,
      ),
    );
    if (profit) this.profitability.set(profit);
  }
  async importReturns(): Promise<void> {
    const current = this.account();
    if (!current) return;
    await this.request(
      () => this.http.get(this.baseUrl + '/accounts/' + current.id + '/returns', this.options),
      'Return records imported.',
    );
    const value = await this.request<AmazonReturn[]>(() =>
      this.http.get<AmazonReturn[]>(
        this.baseUrl + '/accounts/' + current.id + '/returns/records',
        this.options,
      ),
    );
    if (value) this.returns.set(value);
  }
  async loadDrift(): Promise<void> {
    if (this.listingId) {
      const value = await this.request<AmazonDrift>(() =>
        this.http.get<AmazonDrift>(
          this.baseUrl + '/listings/' + this.listingId + '/drift',
          this.options,
        ),
      );
      if (value) this.drift.set(value);
    }
  }
  async keepRemote(): Promise<void> {
    if (this.listingId && window.confirm('Keep the remote Amazon value and record the decision?')) {
      await this.request(
        () =>
          this.http.post(
            this.baseUrl + '/listings/' + this.listingId + '/drift/keep-remote',
            { confirm: true },
            this.options,
          ),
        'Remote values kept.',
      );
      await this.loadDrift();
    }
  }
  async overwriteDrift(): Promise<void> {
    if (
      this.listingId &&
      window.confirm('Overwrite remote Amazon values with the local listing?')
    ) {
      await this.request(
        () =>
          this.http.post(
            this.baseUrl + '/listings/' + this.listingId + '/drift/overwrite',
            { confirm: true, expected_remote_title: this.title || null },
            this.options,
          ),
        'Guarded remote overwrite recorded.',
      );
      await this.loadDrift();
    }
  }
}
