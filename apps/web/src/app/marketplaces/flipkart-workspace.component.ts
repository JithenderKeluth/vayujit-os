import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { generateVariantMatrix } from '../publishing/shopify-variant-matrix';

import { environment } from '../../environments/environment';

interface Account {
  id: string;
  display_name: string;
  seller_account_id: string;
  enabled: boolean;
  credential_status: string;
  validation_status: string;
  last_validated_at?: string | null;
}
interface Listing {
  id: string;
  title: string;
  marketplace_sku: string;
  category?: string | null;
  status: string;
  publication_state: string;
  remote_listing_id: string | null;
  content_artifact_id?: string | null;
  drift_state?: string;
}
interface CatalogItem {
  id: string;
  name: string;
}
interface Readiness {
  ready: boolean;
  blocking: Array<{ code?: string; message: string; field?: string }>;
  warnings?: string[];
  informational?: Array<{ message: string }>;
}
interface Attribute {
  key: string;
  label: string;
  type: string;
  required?: boolean;
  help_text?: string;
  options?: string[];
}
interface Variant {
  stable_variant_key: string;
  sku: string;
  options: string;
  quantity: number;
  listing_state?: string;
  price?: number | null;
  compare_at_price?: number | null;
  barcode?: string;
  remote_variant_id?: string | null;
  readiness?: string;
  drift?: string;
}
interface Order {
  id: string;
  flipkart_order_id: string;
  status: string;
  payment_status: string;
  fulfilment_status: string;
  fulfilments?: Array<{ carrier?: string; tracking_reference?: string }>;
  totals?: { total?: number | string; currency?: string };
  returns?: unknown[];
  refunds?: unknown[];
}
interface Settlement {
  id: string;
  period_start: string;
  period_end: string;
  status: string;
  gross_sales: number | string;
  currency: string;
  refunds: number | string;
  fees: number | string;
  net: number | string;
}
interface InventoryState {
  marketplace_reported_quantity?: number | null;
  synchronization_status?: string | null;
}
interface DriftState {
  drift_state?: string;
  fields?: Array<{ path: string; local?: unknown; remote?: unknown; classification?: string }>;
}
interface Profitability {
  gross_sales: number | string;
  refunds: number | string;
  fees: number | string;
  contribution: number | string;
  profit_status: string;
  estimated_profit?: number | string | null;
  missing_inputs?: string[];
}
interface VariantDraft {
  stable_variant_key: string;
  sku: string;
  options: string;
  quantity: number;
}
interface MediaDraft {
  media_id: string;
  alt_text: string;
  position: number;
}
interface PriceDraft {
  currency: string;
  list_price: number | null;
  selling_price: number | null;
  sale_price: number | null;
}

@Component({
  selector: 'app-flipkart-workspace',
  imports: [FormsModule, RouterLink],
  template: `
    <section class="marketplace-page">
      <header>
        <h1>Flipkart operations</h1>
        <p>
          Local fake-certified workspace. Live Flipkart validation is
          <strong>not performed</strong>.
        </p>
      </header>
      @if (message()) {
        <p class="marketplace-success" role="status">{{ message() }}</p>
      }
      @if (error()) {
        <p class="marketplace-error" role="alert">{{ error() }}</p>
      }

      <nav class="workspace-tabs" aria-label="Flipkart workspace sections">
        @for (tab of tabs; track tab) {
          <button type="button" [class.active-tab]="section() === tab" (click)="section.set(tab)">
            {{ tab }}
          </button>
        }
      </nav>

      @if (section() === 'Overview' || section() === 'Account') {
        <section class="marketplace-card">
          <h2>Account</h2>
          <form class="marketplace-form" (ngSubmit)="createAccount()">
            <label
              >Display name<input name="display" [(ngModel)]="accountDraft.display_name" required
            /></label>
            <label
              >Seller/account ID<input
                name="seller"
                [(ngModel)]="accountDraft.seller_account_id"
                required
            /></label>
            <label
              >Credential (write only)<input
                name="credential"
                type="password"
                [(ngModel)]="accountDraft.credentials.token"
                autocomplete="new-password"
            /></label>
            <button type="submit">Configure</button>
          </form>
          @if (!accounts().length) {
            <p class="marketplace-empty">No Flipkart account configured.</p>
          }
          @for (account of accounts(); track account.id) {
            <article class="workspace-account">
              <div>
                <strong>{{ account.display_name }}</strong
                ><span>{{ account.seller_account_id }}</span>
              </div>
              <div class="workspace-badges">
                <span>{{ account.credential_status }}</span
                ><span>{{ account.validation_status }}</span
                ><span>{{ account.enabled ? 'enabled' : 'disabled' }}</span>
              </div>
              <small
                >Last validated: {{ account.last_validated_at || 'Never' }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· NOT
                LIVE-VALIDATED</small
              >
              <div class="marketplace-actions">
                <button type="button" (click)="validateAccount(account)">Validate</button>
                <button type="button" (click)="revalidateAccount(account)">Revalidate</button>
                <button type="button" (click)="toggleAccount(account)">
                  {{ account.enabled ? 'Disable' : 'Enable' }}
                </button>
                <button type="button" (click)="replaceCredential(account)">
                  Replace credential
                </button>
                <button type="button" (click)="removeCredential(account)">Remove credential</button>
              </div>
            </article>
          }
        </section>
      }

      @if (section() === 'Overview' || section() === 'Listings' || section() === 'Listing Editor') {
        <section class="marketplace-card">
          <h2>Listings</h2>
          <div class="marketplace-table">
            <table>
              <caption>
                Flipkart listings
              </caption>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>SKU</th>
                  <th>Lifecycle</th>
                  <th>Remote ID</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                @for (listing of listings(); track listing.id) {
                  <tr>
                    <td>{{ listing.title }}</td>
                    <td>{{ listing.marketplace_sku }}</td>
                    <td>
                      {{ listing.status }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· {{ listing.publication_state }}
                    </td>
                    <td>{{ listing.remote_listing_id || 'Not submitted' }}</td>
                    <td><button type="button" (click)="selectListing(listing)">Edit</button></td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          <h3>Create listing</h3>
          <form class="workspace-grid-form" (ngSubmit)="createListing()">
            <label
              >Product<select name="product" [(ngModel)]="listingDraft.product_id" required>
                <option value="">Select Product</option>
                @for (item of products(); track item.id) {
                  <option [value]="item.id">{{ item.name }}</option>
                }
              </select></label
            >
            <label
              >Brand<select name="brand" [(ngModel)]="listingDraft.brand_id" required>
                <option value="">Select Brand</option>
                @for (item of brands(); track item.id) {
                  <option [value]="item.id">{{ item.name }}</option>
                }
              </select></label
            >
            <label
              >Account<select name="account" [(ngModel)]="listingDraft.account_id" required>
                <option value="">Select account</option>
                @for (item of accounts(); track item.id) {
                  <option [value]="item.id">{{ item.display_name }}</option>
                }
              </select></label
            >
            <label
              >Approved Artifact ID<input
                name="artifact"
                [(ngModel)]="listingDraft.artifact_id"
                required
            /></label>
            <label>Title<input name="title" [(ngModel)]="listingDraft.title" required /></label>
            <label
              >Category<select
                name="category"
                [(ngModel)]="listingDraft.category"
                (ngModelChange)="loadAttributes()"
                required
              >
                <option value="">Select category</option>
                @for (item of categories(); track item.id) {
                  <option [value]="item.id">{{ item.name }}</option>
                }
              </select></label
            >
            <label
              >Seller SKU<input name="sku" [(ngModel)]="listingDraft.marketplace_sku" required
            /></label>
            <button type="submit">Create draft</button>
          </form>
        </section>
      }

      @if (activeListing(); as listing) {
        @if (section() === 'Listing Editor' || section() === 'Overview') {
          <section class="marketplace-card">
            <h2>Listing editor: {{ listing.title }}</h2>
            <p>
              Product channel ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· SKU
              {{ listing.marketplace_sku }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· Artifact
              {{ listing.content_artifact_id || 'not attached' }}
            </p>
            <div class="workspace-tabs inner-tabs" aria-label="Listing editor sections">
              @for (tab of editorTabs; track tab) {
                <button
                  type="button"
                  [class.active-tab]="editorSection() === tab"
                  (click)="editorSection.set(tab)"
                >
                  {{ tab }}
                </button>
              }
            </div>
            @if (editorSection() === 'Product') {
              <p class="marketplace-callout">
                Canonical Product and Brand are preserved. Marketplace-specific state is
                independent.
              </p>
            }
            @if (editorSection() === 'Category') {
              <label class="field-label"
                >Category<select
                  [(ngModel)]="listingDraft.category"
                  (ngModelChange)="loadAttributes()"
                >
                  @for (item of categories(); track item.id) {
                    <option [value]="item.id">{{ item.name }}</option>
                  }
                </select></label
              >
            }
            @if (editorSection() === 'Attributes') {
              <div class="workspace-attribute-grid">
                @for (attribute of attributes(); track attribute.key) {
                  <label class="field-label"
                    >{{ attribute.label }}
                    @if (attribute.required) {
                      <span aria-label="required">*</span>
                    }
                    <input
                      [type]="inputType(attribute.type)"
                      [(ngModel)]="attributeValues[attribute.key]"
                      [name]="attribute.key"
                      [attr.aria-describedby]="attribute.help_text ? attribute.key + '-help' : null"
                    />
                    @if (attribute.help_text) {
                      <small [id]="attribute.key + '-help'">{{ attribute.help_text }}</small>
                    }
                  </label>
                }
              </div>
            }
            @if (editorSection() === 'Content') {
              <p class="marketplace-callout">
                Content uses the exact approved Artifact attached to this listing. Raw provider
                output is never shown.
              </p>
            }
            @if (editorSection() === 'Variants') {
              <form class="workspace-grid-form" (ngSubmit)="buildVariantMatrix()">
                <label class="field-label"
                  >Dimensions
                  <input
                    name="matrixDimensions"
                    [(ngModel)]="matrixDimensionsText"
                    placeholder="Size=S|M|L;Color=Red|Blue"
                    aria-describedby="matrix-help"
                  />
                  <small id="matrix-help"
                    >Use name=value|value;name=value|value. Maximum 100 combinations.</small
                  >
                </label>
                <button type="submit">Build variant matrix</button>
              </form>
              @if (matrixError()) {
                <p class="marketplace-error" role="alert">{{ matrixError() }}</p>
              }
              <div class="marketplace-table">
                <table>
                  <caption>
                    Deterministic variant matrix
                  </caption>
                  <thead>
                    <tr>
                      <th>Combination</th>
                      <th>Seller SKU</th>
                      <th>Barcode</th>
                      <th>MRP</th>
                      <th>Selling</th>
                      <th>Qty</th>
                      <th>Readiness</th>
                      <th>Remote</th>
                      <th>Drift</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (
                      variant of variants();
                      track variant.stable_variant_key;
                      let index = $index
                    ) {
                      <tr>
                        <td>
                          <code>{{ variant.options }}</code>
                        </td>
                        <td>
                          <input
                            [name]="'sku-' + index"
                            [(ngModel)]="variant.sku"
                            aria-label="Seller SKU"
                          />
                        </td>
                        <td>
                          <input
                            [name]="'barcode-' + index"
                            [(ngModel)]="variant.barcode"
                            aria-label="Barcode"
                          />
                        </td>
                        <td>
                          <input
                            [name]="'mrp-' + index"
                            type="number"
                            [(ngModel)]="variant.compare_at_price"
                            aria-label="MRP"
                          />
                        </td>
                        <td>
                          <input
                            [name]="'price-' + index"
                            type="number"
                            [(ngModel)]="variant.price"
                            aria-label="Selling price"
                          />
                        </td>
                        <td>
                          <input
                            [name]="'qty-' + index"
                            type="number"
                            min="0"
                            [(ngModel)]="variant.quantity"
                            aria-label="Quantity"
                          />
                        </td>
                        <td>{{ variant.readiness || 'Draft' }}</td>
                        <td>{{ variant.remote_variant_id || 'Not submitted' }}</td>
                        <td>{{ variant.drift || 'Not checked' }}</td>
                        <td>
                          <button
                            type="button"
                            (click)="removeVariant(variant)"
                            aria-label="Remove variant"
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
              <button type="button" (click)="saveVariantMatrix()" [disabled]="!variants().length">
                Save variant matrix
              </button>
            }
            @if (editorSection() === 'Media') {
              <form class="workspace-grid-form" (ngSubmit)="addMedia()">
                <label
                  >Media asset ID<input
                    name="mediaId"
                    [(ngModel)]="mediaDraft.media_id"
                    required /></label
                ><label
                  >Alt/internal label<input name="alt" [(ngModel)]="mediaDraft.alt_text" /></label
                ><label
                  >Position<input
                    name="position"
                    type="number"
                    [(ngModel)]="mediaDraft.position"
                    min="0" /></label
                ><button type="submit">Add media mapping</button>
              </form>
              <p class="marketplace-callout">
                Removing a mapping never deletes the local Media Asset.
              </p>
            }
            @if (editorSection() === 'Pricing') {
              <form class="workspace-grid-form" (ngSubmit)="savePrice()">
                <label
                  >Currency<input
                    name="currency"
                    [(ngModel)]="priceDraft.currency"
                    maxlength="3" /></label
                ><label
                  >MRP/list price<input
                    name="list"
                    type="number"
                    [(ngModel)]="priceDraft.list_price"
                    min="0" /></label
                ><label
                  >Selling price<input
                    name="selling"
                    type="number"
                    [(ngModel)]="priceDraft.selling_price"
                    min="0"
                    required /></label
                ><label
                  >Sale price<input
                    name="sale"
                    type="number"
                    [(ngModel)]="priceDraft.sale_price"
                    min="0" /></label
                ><button type="submit">Review and confirm price</button>
              </form>
            }
            @if (editorSection() === 'Inventory') {
              <form class="workspace-grid-form" (ngSubmit)="saveInventory()">
                <label
                  >Target quantity<input
                    name="quantity"
                    type="number"
                    [(ngModel)]="inventoryDraft.quantity"
                    min="0"
                    required /></label
                ><button type="submit">Preview and confirm inventory</button>
              </form>
              <p>
                Remote quantity:
                {{ inventory()?.marketplace_reported_quantity ?? 'Unknown' }} ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â·
                State:
                {{ inventory()?.synchronization_status || 'Not synchronized' }}
              </p>
            }
            @if (editorSection() === 'Readiness' || editorSection() === 'Preview') {
              <button type="button" (click)="preview()">Refresh readiness</button>
              @if (readiness(); as value) {
                <div class="readiness-grid">
                  <div>
                    <h3>Blocking issues</h3>
                    <ul>
                      @for (issue of value.blocking; track issue.message) {
                        <li>{{ issue.message }}</li>
                      }
                    </ul>
                  </div>
                  <div>
                    <h3>Warnings</h3>
                    <ul>
                      @for (issue of value.warnings || []; track issue) {
                        <li>{{ issue }}</li>
                      }
                    </ul>
                  </div>
                  <div>
                    <h3>Information</h3>
                    <ul>
                      @for (issue of value.informational || []; track issue.message) {
                        <li>{{ issue.message }}</li>
                      }
                    </ul>
                  </div>
                </div>
                <p class="marketplace-status">
                  {{ value.ready ? 'Ready for submission' : 'Submission blocked' }}
                </p>
              }
            }
            <div class="marketplace-actions">
              <button type="button" [disabled]="!readiness()?.ready" (click)="submit()">
                Confirm and submit</button
              ><button type="button" (click)="reconcile()">Refresh remote state</button
              ><button type="button" (click)="reviewDrift()">Review drift</button
              ><button type="button" (click)="keepRemote()">Keep remote</button
              ><button type="button" (click)="overwrite()">Confirmed overwrite</button>
            </div>
            @if (drift(); as value) {
              <div class="marketplace-callout">
                <strong>Drift: {{ value.drift_state }}</strong>
                @for (field of value.fields || []; track field.path) {
                  <p>
                    {{ field.path }}: local
                    {{ field.local || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }}
                    ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â· remote
                    {{ field.remote || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }} ({{
                      field.classification
                    }})
                  </p>
                }
              </div>
            }
          </section>
        }
      }

      @if (section() === 'Orders' || section() === 'Overview') {
        <section class="marketplace-card">
          <h2>Orders and fulfilment</h2>
          <button type="button" (click)="importOrders()">Import orders</button>
          <div class="marketplace-table">
            <table>
              <caption>
                Read-only Flipkart orders
              </caption>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Status</th>
                  <th>Payment</th>
                  <th>Fulfilment</th>
                  <th>Total</th>
                  <th>Returns/refunds</th>
                </tr>
              </thead>
              <tbody>
                @for (order of orders(); track order.id) {
                  <tr>
                    <td>{{ order.flipkart_order_id }}</td>
                    <td>{{ order.status }}</td>
                    <td>{{ order.payment_status }}</td>
                    <td>
                      {{ order.fulfilment_status }} {{ order.fulfilments?.[0]?.carrier || '' }}
                      {{ order.fulfilments?.[0]?.tracking_reference || '' }}
                    </td>
                    <td>
                      {{ order.totals?.total || 'ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â' }}
                      {{ order.totals?.currency || '' }}
                    </td>
                    <td>{{ order.returns?.length || 0 }} / {{ order.refunds?.length || 0 }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </section>
      }
      @if (section() === 'Financials' || section() === 'Overview') {
        <section class="marketplace-card">
          <h2>Financials and profitability</h2>
          <button type="button" (click)="importFinancials()">Import settlements</button>
          <div class="marketplace-table">
            <table>
              <caption>
                Settlement summaries
              </caption>
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Status</th>
                  <th>Gross</th>
                  <th>Refunds</th>
                  <th>Fees</th>
                  <th>Net</th>
                </tr>
              </thead>
              <tbody>
                @for (item of settlements(); track item.id) {
                  <tr>
                    <td>
                      {{ item.period_start }} ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ
                      {{ item.period_end }}
                    </td>
                    <td>{{ item.status }}</td>
                    <td>{{ item.gross_sales }} {{ item.currency }}</td>
                    <td>{{ item.refunds }}</td>
                    <td>{{ item.fees }}</td>
                    <td>{{ item.net }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          @if (profitability(); as value) {
            <dl class="marketplace-stats">
              <div>
                <dt>Gross sales</dt>
                <dd>{{ value.gross_sales }}</dd>
              </div>
              <div>
                <dt>Refunds</dt>
                <dd>{{ value.refunds }}</dd>
              </div>
              <div>
                <dt>Fees</dt>
                <dd>{{ value.fees }}</dd>
              </div>
              <div>
                <dt>Contribution</dt>
                <dd>{{ value.contribution }}</dd>
              </div>
              <div>
                <dt>Estimated profit</dt>
                <dd>
                  {{ value.profit_status === 'available' ? value.estimated_profit : 'Unavailable' }}
                </dd>
              </div>
            </dl>
            <p>{{ value.missing_inputs?.join(', ') }}</p>
          }
        </section>
      }
      @if (section() === 'Diagnostics' || section() === 'Overview') {
        <section class="marketplace-card">
          <h2>Diagnostics</h2>
          @if (diagnostics(); as value) {
            <dl class="marketplace-stats">
              @for (item of diagnosticEntries(value); track item[0]) {
                <div>
                  <dt>{{ item[0] }}</dt>
                  <dd>{{ item[1] }}</dd>
                </div>
              }
            </dl>
          }
          <p class="marketplace-callout">
            Credentials are write-only. No buyer PII, tokens, cookies, SQL, or local paths are
            shown.
          </p>
        </section>
      }
      <p><a routerLink="/marketplaces">Back to Marketplace overview</a></p>
    </section>
  `,
  styleUrl: './marketplaces.css',
})
export class FlipkartWorkspaceComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly base = `${environment.apiUrl}/marketplaces/flipkart`;
  private readonly options = { withCredentials: true } as const;
  readonly tabs = [
    'Overview',
    'Account',
    'Listings',
    'Listing Editor',
    'Inventory',
    'Orders',
    'Financials',
    'Diagnostics',
  ];
  readonly editorTabs = [
    'Product',
    'Category',
    'Attributes',
    'Content',
    'Variants',
    'Media',
    'Pricing',
    'Inventory',
    'Readiness',
    'Preview',
  ];
  readonly section = signal('Overview');
  readonly editorSection = signal('Product');
  readonly accounts = signal<Account[]>([]);
  readonly listings = signal<Listing[]>([]);
  readonly products = signal<CatalogItem[]>([]);
  readonly brands = signal<CatalogItem[]>([]);
  readonly categories = signal<CatalogItem[]>([]);
  readonly attributes = signal<Attribute[]>([]);
  readonly variants = signal<Variant[]>([]);
  readonly orders = signal<Order[]>([]);
  readonly settlements = signal<Settlement[]>([]);
  readonly readiness = signal<Readiness | null>(null);
  readonly inventory = signal<InventoryState | null>(null);
  readonly drift = signal<DriftState | null>(null);
  readonly diagnostics = signal<Record<string, unknown> | null>(null);
  readonly profitability = signal<Profitability | null>(null);
  readonly activeListing = signal<Listing | null>(null);
  readonly message = signal('');
  readonly error = signal('');
  readonly accountDraft = { display_name: '', seller_account_id: '', credentials: { token: '' } };
  readonly listingDraft = {
    brand_id: '',
    product_id: '',
    account_id: '',
    artifact_id: '',
    title: '',
    category: '',
    marketplace_sku: '',
  };
  matrixDimensionsText = '';
  readonly matrixError = signal('');
  readonly variantDraft: VariantDraft = {
    stable_variant_key: '',
    sku: '',
    options: '',
    quantity: 0,
  };
  readonly mediaDraft: MediaDraft = { media_id: '', alt_text: '', position: 0 };
  readonly priceDraft: PriceDraft = {
    currency: 'INR',
    list_price: null,
    selling_price: null,
    sale_price: null,
  };
  readonly inventoryDraft = { quantity: 0 };
  readonly attributeValues: Record<string, string | number> = {};
  private readonly listingId = this.route.snapshot.paramMap.get('id');

  ngOnInit(): void {
    void this.loadWorkspace();
  }

  async loadWorkspace(): Promise<void> {
    await this.act(async () => {
      const [accounts, listings] = await Promise.all([
        firstValueFrom(this.http.get<Account[]>(`${this.base}/accounts`, this.options)),
        firstValueFrom(this.http.get<Listing[]>(`${this.base}/listings`, this.options)),
      ]);
      this.accounts.set(accounts);
      this.listings.set(listings);
      this.products.set(await this.safeGet<CatalogItem[]>(`${environment.apiUrl}/products`));
      this.brands.set(await this.safeGet<CatalogItem[]>(`${environment.apiUrl}/brands`));
      if (accounts[0]) {
        this.listingDraft.account_id ||= accounts[0].id;
        this.categories.set(
          await this.safeGet<CatalogItem[]>(`${this.base}/accounts/${accounts[0].id}/categories`),
        );
      }
      if (this.listingId) {
        const listing = listings.find((item) => item.id === this.listingId);
        if (listing) {
          this.selectListing(listing);
        }
      }
    });
  }
  async createAccount(): Promise<void> {
    await this.act(async () => {
      await firstValueFrom(
        this.http.post(`${this.base}/accounts`, this.accountDraft, this.options),
      );
      this.accountDraft.display_name = '';
      this.accountDraft.seller_account_id = '';
      this.accountDraft.credentials.token = '';
      await this.loadWorkspace();
      this.message.set('Account configured. Validate before enabling.');
    });
  }
  async validateAccount(account: Account): Promise<void> {
    await this.accountAction(account, 'validate', 'Account validated.');
  }
  async revalidateAccount(account: Account): Promise<void> {
    await this.accountAction(account, 'revalidate', 'Account revalidated.');
  }
  async toggleAccount(account: Account): Promise<void> {
    await this.accountAction(
      account,
      account.enabled ? 'disable' : 'enable',
      account.enabled ? 'Account disabled.' : 'Account enabled.',
    );
  }
  async replaceCredential(account: Account): Promise<void> {
    const token = window.prompt(
      'Enter the replacement credential. It will not be displayed again.',
    );
    if (token) {
      await this.act(async () => {
        await firstValueFrom(
          this.http.put(`${this.base}/accounts/${account.id}/credential`, { token }, this.options),
        );
        await this.loadWorkspace();
        this.message.set('Credential replaced; history was preserved.');
      });
    }
  }
  async removeCredential(account: Account): Promise<void> {
    if (window.confirm('Remove the credential? Account history will remain.')) {
      await this.act(async () => {
        await firstValueFrom(
          this.http.delete(`${this.base}/accounts/${account.id}/credential`, {
            ...this.options,
            body: { confirm: true },
          }),
        );
        await this.loadWorkspace();
        this.message.set('Credential removed and account disabled.');
      });
    }
  }
  private async accountAction(account: Account, action: string, success: string): Promise<void> {
    await this.act(async () => {
      await firstValueFrom(
        this.http.post(
          `${this.base}/accounts/${account.id}/${action}`,
          action === 'enable' || action === 'disable' ? { confirm: true } : {},
          this.options,
        ),
      );
      await this.loadWorkspace();
      this.message.set(success);
    });
  }
  async createListing(): Promise<void> {
    await this.act(async () => {
      const listing = await firstValueFrom(
        this.http.post<Listing>(`${this.base}/listings`, this.listingDraft, this.options),
      );
      this.listings.update((items) => [listing, ...items]);
      this.selectListing(listing);
      await this.router.navigate(['/marketplaces/listings', listing.id, 'flipkart']);
      this.message.set('Draft created. Complete the editor and readiness checks.');
    });
  }
  selectListing(listing: Listing): void {
    this.activeListing.set(listing);
    this.listingDraft.category = listing.category || '';
    this.listingDraft.title = listing.title;
    this.listingDraft.marketplace_sku = listing.marketplace_sku;
    this.section.set('Listing Editor');
    void this.loadListingData(listing);
  }
  async loadListingData(listing: Listing): Promise<void> {
    await this.act(async () => {
      const account = this.listingDraft.account_id || this.accounts()[0]?.id;
      if (!account) return;
      this.categories.set(
        await this.safeGet<CatalogItem[]>(`${this.base}/accounts/${account}/categories`),
      );
      this.readiness.set(
        await this.safeGet<Readiness>(`${this.base}/listings/${listing.id}/readiness`),
      );
      this.drift.set(await this.safeGet<DriftState>(`${this.base}/listings/${listing.id}/drift`));
    });
  }
  async loadAttributes(): Promise<void> {
    const account = this.listingDraft.account_id || this.accounts()[0]?.id;
    if (account && this.listingDraft.category) {
      this.attributes.set(
        (
          await this.safeGet<{ attributes: Attribute[] }>(
            `${this.base}/accounts/${account}/categories/${this.listingDraft.category}/attributes`,
          )
        ).attributes || [],
      );
    }
  }
  buildVariantMatrix(): void {
    this.matrixError.set('');
    const definitions = this.matrixDimensionsText
      .split(';')
      .filter(Boolean)
      .map((part) => {
        const [name, values] = part.split('=').map((value) => value?.trim() || '');
        return {
          name,
          values: values
            .split('|')
            .map((value) => value.trim())
            .filter(Boolean),
        };
      });
    const result = generateVariantMatrix(
      definitions,
      this.variants().map((item) => ({
        local_key: item.stable_variant_key,
        options: item.options
          .split(',')
          .filter(Boolean)
          .map((value) => {
            const [name, option] = value.split('=');
            return { name: name?.trim() || 'Option', value: option?.trim() || value.trim() };
          }),
        sku: item.sku || null,
        price: item.price == null ? null : String(item.price),
        compare_at_price: item.compare_at_price == null ? null : String(item.compare_at_price),
        barcode: item.barcode || null,
        weight: null,
        weight_unit: null,
        taxable: true,
        track_inventory: true,
      })),
      this.priceDraft.selling_price == null ? null : String(this.priceDraft.selling_price),
    );
    if (result.errors.length) {
      this.matrixError.set(result.errors.join(' '));
      return;
    }
    if (
      result.removedKeys.length &&
      !window.confirm(`Regenerating removes ${result.removedKeys.length} obsolete rows. Continue?`)
    )
      return;
    this.variants.set(
      result.variants.map((row) => ({
        stable_variant_key: row.local_key,
        sku: row.sku || '',
        options: row.options.map((option) => `${option.name}=${option.value}`).join(', '),
        quantity: 0,
        price: row.price == null ? null : Number(row.price),
        compare_at_price: row.compare_at_price == null ? null : Number(row.compare_at_price),
        barcode: row.barcode || '',
        readiness: 'Draft',
        drift: 'Not checked',
      })),
    );
  }
  async saveVariantMatrix(): Promise<void> {
    if (!this.activeListing()) return;
    await this.act(async () => {
      const variants = this.variants().map((item) => ({
        stable_variant_key: item.stable_variant_key,
        sku: item.sku,
        options: Object.fromEntries(
          item.options.split(',').map((part) => {
            const [key, value] = part.split('=');
            return [key?.trim() || 'Option', value?.trim() || ''];
          }),
        ),
        price: item.price ?? 0,
        compare_at_price: item.compare_at_price,
        barcode: item.barcode || null,
      }));
      await firstValueFrom(
        this.http.put(
          `${this.base}/listings/${this.activeListing()!.id}/variants`,
          { variants, idempotency_key: `flipkart-variant-matrix-${this.activeListing()!.id}` },
          this.options,
        ),
      );
      this.message.set('Variant matrix saved.');
    });
  }
  async addVariant(): Promise<void> {
    if (!this.activeListing()) return;
    await this.act(async () => {
      const item = {
        stable_variant_key: this.variantDraft.stable_variant_key,
        sku: this.variantDraft.sku,
        options: this.variantDraft.options,
        price: this.priceDraft.selling_price,
        quantity: this.variantDraft.quantity,
      };
      await firstValueFrom(
        this.http.put(
          `${this.base}/listings/${this.activeListing()!.id}/variants`,
          {
            variants: [item],
            idempotency_key: `flipkart-variant-${this.activeListing()!.id}-${item.stable_variant_key}`,
          },
          this.options,
        ),
      );
      this.variants.update((items) => [...items, item]);
      this.message.set('Variant saved.');
    });
  }
  removeVariant(variant: Variant): void {
    this.variants.update((items) => items.filter((item) => item !== variant));
  }
  async addMedia(): Promise<void> {
    if (!this.activeListing()) return;
    await this.act(async () => {
      await firstValueFrom(
        this.http.put(
          `${this.base}/listings/${this.activeListing()!.id}/media`,
          {
            media: [this.mediaDraft],
            idempotency_key: `flipkart-media-${this.activeListing()!.id}-${this.mediaDraft.media_id}`,
          },
          this.options,
        ),
      );
      this.message.set('Media mapping saved.');
    });
  }
  async savePrice(): Promise<void> {
    if (!this.activeListing()) return;
    await this.act(async () => {
      await firstValueFrom(
        this.http.put(
          `${this.base}/listings/${this.activeListing()!.id}/pricing`,
          {
            ...this.priceDraft,
            confirm: true,
            idempotency_key: `flipkart-price-${this.activeListing()!.id}-${this.priceDraft.selling_price}`,
          },
          this.options,
        ),
      );
      this.message.set('Price queued and confirmed.');
    });
  }
  async saveInventory(): Promise<void> {
    if (!this.activeListing()) return;
    await this.act(async () => {
      const value = await firstValueFrom(
        this.http.post<InventoryState>(
          `${this.base}/listings/${this.activeListing()!.id}/inventory`,
          {
            quantity: this.inventoryDraft.quantity,
            confirm: true,
            idempotency_key: `flipkart-inventory-${this.activeListing()!.id}-${this.inventoryDraft.quantity}`,
          },
          this.options,
        ),
      );
      this.inventory.set(value);
      this.message.set('Inventory update completed safely.');
    });
  }
  async preview(): Promise<void> {
    if (!this.activeListing()) return;
    await this.act(async () => {
      const value = await firstValueFrom(
        this.http.post<{ readiness: Readiness }>(
          `${this.base}/listings/${this.activeListing()!.id}/preview`,
          {
            category_id: this.listingDraft.category,
            attributes: this.attributeValues,
            variants: this.variants(),
            media: [],
            price: this.priceDraft,
          },
          this.options,
        ),
      );
      this.readiness.set(value.readiness);
      this.editorSection.set('Readiness');
    });
  }
  async submit(): Promise<void> {
    if (!this.activeListing()) return;
    await this.act(async () => {
      await firstValueFrom(
        this.http.post(
          `${this.base}/listings/${this.activeListing()!.id}/submit`,
          {
            category_id: this.listingDraft.category,
            attributes: this.attributeValues,
            variants: this.variants(),
            media: [],
            price: this.priceDraft,
            idempotency_key: `flipkart-ui-submit-${this.activeListing()!.id}`,
          },
          this.options,
        ),
      );
      this.message.set(
        'Submission queued. The workspace will show processing or rejection safely.',
      );
      await this.loadWorkspace();
    });
  }
  async reconcile(): Promise<void> {
    if (!this.activeListing()) return;
    await this.act(async () => {
      await firstValueFrom(
        this.http.post(
          `${this.base}/listings/${this.activeListing()!.id}/reconcile`,
          {},
          this.options,
        ),
      );
      this.drift.set(await this.safeGet(`${this.base}/listings/${this.activeListing()!.id}/drift`));
      this.message.set('Remote state refreshed.');
    });
  }
  async reviewDrift(): Promise<void> {
    if (!this.activeListing()) return;
    await this.act(async () => {
      this.drift.set(
        await firstValueFrom(
          this.http.post<DriftState>(
            `${this.base}/listings/${this.activeListing()!.id}/drift/review`,
            {},
            this.options,
          ),
        ),
      );
    });
  }
  async keepRemote(): Promise<void> {
    if (!this.activeListing() || !window.confirm('Keep remote values?')) return;
    await this.act(async () => {
      await firstValueFrom(
        this.http.post(
          `${this.base}/listings/${this.activeListing()!.id}/drift/keep-remote`,
          { confirm: true },
          this.options,
        ),
      );
      this.message.set('Remote values kept.');
    });
  }
  async overwrite(): Promise<void> {
    if (
      !this.activeListing() ||
      !window.confirm('Overwrite remote values with the approved local listing?')
    )
      return;
    await this.act(async () => {
      await firstValueFrom(
        this.http.post(
          `${this.base}/listings/${this.activeListing()!.id}/drift/overwrite`,
          { confirm: true },
          this.options,
        ),
      );
      this.message.set('Remote values overwritten after confirmation.');
    });
  }
  async importOrders(): Promise<void> {
    const account = this.accounts()[0];
    if (account)
      await this.act(async () => {
        await firstValueFrom(
          this.http.post(`${this.base}/accounts/${account.id}/orders/import`, {}, this.options),
        );
        this.orders.set(await this.safeGet(`${this.base}/accounts/${account.id}/orders`));
      });
  }
  async importFinancials(): Promise<void> {
    const account = this.accounts()[0];
    if (account)
      await this.act(async () => {
        await firstValueFrom(
          this.http.post(
            `${this.base}/accounts/${account.id}/financial-events/import`,
            {},
            this.options,
          ),
        );
        this.settlements.set(await this.safeGet(`${this.base}/accounts/${account.id}/settlements`));
        this.profitability.set(
          await this.safeGet(`${this.base}/accounts/${account.id}/profitability`),
        );
      });
  }
  diagnosticEntries(value: Record<string, unknown>): Array<[string, unknown]> {
    return Object.entries(value);
  }
  inputType(type: string): string {
    return type === 'number' || type === 'money' || type === 'weight'
      ? 'number'
      : type === 'date'
        ? 'date'
        : 'text';
  }
  private async safeGet<T>(url: string): Promise<T> {
    try {
      return await firstValueFrom(this.http.get<T>(url, this.options));
    } catch {
      return [] as T;
    }
  }
  private async act(action: () => Promise<void>): Promise<void> {
    this.error.set('');
    try {
      await action();
    } catch {
      this.error.set(
        'Unable to complete the Flipkart request. Check the safe API error and readiness blockers.',
      );
    }
  }
}
