import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import type { CatalogVariant, ProductSummary } from '@vayujit/shared';
import { AuthService } from '../auth/auth.service';
import { CatalogService } from '../catalog/catalog.service';
import { ProductService } from '../products/product.service';
import { PageHeaderComponent } from '../shared/page-header.component';
import {
  InventoryItem,
  InventoryMovement,
  InventoryOpeningRequest,
  MarketplaceService,
} from './marketplace.service';

const limit = 2_000_000_000;
export function wholeStock(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= limit;
}
function storedRequest(value: unknown): value is InventoryOpeningRequest {
  if (!value || typeof value !== 'object') return false;
  const p = value as Record<string, unknown>;
  return (
    typeof p['product_id'] === 'string' &&
    typeof p['idempotency_key'] === 'string' &&
    p['idempotency_key'].startsWith('ui-opening-') &&
    (p['variant_id'] === null || typeof p['variant_id'] === 'string') &&
    ['internal_sku', 'location_code', 'unit'].every(
      (key) => typeof p[key] === 'string' && !!p[key].trim(),
    ) &&
    wholeStock(p['opening_quantity']) &&
    wholeStock(p['low_stock_threshold'])
  );
}

@Component({
  selector: 'app-opening-stock',
  imports: [DatePipe, FormsModule, RouterLink, PageHeaderComponent],
  styleUrls: ['./marketplaces.css', './opening-stock.css'],
  template: `
    <section class="marketplace-page opening-page" aria-label="Opening stock workspace">
      <app-page-header
        title="Add opening stock"
        eyebrow="Inventory / Local stock"
        description="Record the physical units you have counted. Review before anything is saved."
      />
      <a routerLink="/marketplaces/inventory" [queryParams]="returnFilters">Back to inventory</a>
      <p class="marketplace-callout" role="note">
        Local record only. This does not buy stock, publish marketplace quantities, certify costs,
        or contact a supplier. Product master quantity is separate from this canonical inventory
        ledger.
      </p>
      @if (notice()) {
        <p role="status">{{ notice() }}</p>
      }
      @if (error()) {
        <div role="alert" class="marketplace-error" tabindex="-1" id="opening-error">
          <h2>Opening stock needs attention</h2>
          <p>{{ error() }}</p>
        </div>
      }
      @if (loading()) {
        <p role="status">Loading owned catalog products and current stock…</p>
      }
      @if (saved(); as item) {
        <section class="marketplace-card" aria-labelledby="opening-success">
          <h2 id="opening-success" tabindex="-1">Opening stock recorded</h2>
          <p role="status">
            Verified from the saved inventory and its opening movement. No marketplace was
            contacted.
          </p>
          <p>
            <strong>{{ product()?.name }}</strong> · {{ item.internal_sku }} ·
            {{ item.location_code }}
          </p>
          @if (opening(); as movement) {
            <dl class="opening-facts">
              <div>
                <dt>Original opening count</dt>
                <dd>{{ movement.quantity }} {{ item.unit }}</dd>
              </div>
              <div>
                <dt>Current on hand</dt>
                <dd>{{ item.on_hand_quantity }}</dd>
              </div>
              <div>
                <dt>Reserved / damaged</dt>
                <dd>{{ item.reserved_quantity }} / {{ item.damaged_quantity }}</dd>
              </div>
              <div>
                <dt>Available to promise</dt>
                <dd>{{ item.available_to_promise }}</dd>
              </div>
            </dl>
            <p>
              Movement reference: <span class="reference">{{ movement.id }}</span>
            </p>
            <p>
              {{ movement.reason }} · {{ movement.actor_type }} ·
              {{ movement.created_at | date: 'medium' }} · current version {{ item.version }}
            </p>
            @if (item.version > 1) {
              <p role="note">
                Stock has changed since opening. The original movement is preserved; the current
                balance above includes later activity.
              </p>
            }
          }
          <h3>What next?</h3>
          <p>
            Use View ledger or Adjust stock on the inventory list for later receipts or corrections.
            Do not enter the opening balance again.
          </p>
          <a routerLink="/marketplaces/inventory" [queryParams]="returnFilters"
            >Return to inventory</a
          >
        </section>
      } @else if (!loading()) {
        @if (review(); as change) {
          <section class="marketplace-card" aria-labelledby="opening-review">
            <h2 id="opening-review" tabindex="-1">Review opening stock</h2>
            <p>
              <strong>{{ product()?.name }}</strong> · {{ product()?.brand_name }} · Product
              reference <span class="reference">{{ change.product_id }}</span>
            </p>
            <dl class="opening-facts">
              <div>
                <dt>Variant</dt>
                <dd>{{ variantName() }}</dd>
              </div>
              <div>
                <dt>Internal SKU</dt>
                <dd>{{ change.internal_sku }}</dd>
              </div>
              <div>
                <dt>Location</dt>
                <dd>{{ change.location_code }}</dd>
              </div>
              <div>
                <dt>Counted opening quantity</dt>
                <dd>{{ change.opening_quantity }} {{ change.unit }}</dd>
              </div>
              <div>
                <dt>Low-stock alert threshold</dt>
                <dd>{{ change.low_stock_threshold }}</dd>
              </div>
              <div>
                <dt>Movement reason</dt>
                <dd>Opening balance</dd>
              </div>
            </dl>
            <p>
              This creates one new stock record at this SKU and location. It cannot replace an
              existing balance. Reserved and damaged quantities start at zero; cost and supplier
              information are not assumed.
            </p>
            <label class="checkbox-label"
              ><input type="checkbox" [(ngModel)]="confirmed" [disabled]="busy()" /> I have counted
              these units and confirm this local opening balance.</label
            >
            <div class="marketplace-actions">
              <button type="button" (click)="submit()" [disabled]="busy() || !confirmed">
                {{
                  busy()
                    ? 'Saving and verifying…'
                    : uncertain()
                      ? 'Retry identical opening request'
                      : 'Confirm opening stock'
                }}</button
              ><button type="button" (click)="edit()" [disabled]="busy() || uncertain()">
                Edit review
              </button>
            </div>
            @if (uncertain()) {
              <p role="note">
                The previous confirmation may have reached the API. Only retry this identical
                request; its retained key prevents duplicate opening movements. Returning to the
                list does not submit anything.
              </p>
            }
          </section>
        } @else {
          <form
            class="marketplace-card opening-form"
            aria-label="Opening stock details"
            novalidate
            (ngSubmit)="prepare()"
          >
            <fieldset [disabled]="busy()">
              <legend>Opening balance details</legend>
              <h2>1. Choose an existing product</h2>
              <p>
                Unpublished physical products are eligible. Archived, digital, service and affiliate
                products are not. Costs, a supplier and marketplace accounts are not prerequisites.
              </p>
              <div class="marketplace-form">
                <label
                  >Find product by name or SKU<input name="search" [(ngModel)]="search" /></label
                ><button type="button" (click)="findProducts()">Find products</button>
              </div>
              <label for="opening-product">Catalog product</label
              ><select
                id="opening-product"
                name="product"
                [ngModel]="productId"
                (ngModelChange)="choose($event)"
                [attr.aria-invalid]="errors()['product'] ? 'true' : null"
                aria-describedby="product-error"
              >
                <option value="">Select a physical product</option>
                @for (item of products(); track item.id) {
                  <option [value]="item.id">
                    {{ item.name }} · {{ item.sku || 'No product SKU' }} · {{ item.brand_name }}
                  </option>
                }
              </select>
              <p id="product-error" class="marketplace-error">{{ errors()['product'] }}</p>
              @if (!products().length && !error()) {
                <p>
                  No eligible products match this search.
                  <a routerLink="/products/new">Create a product</a>, then return here.
                </p>
              }
              <p>Product results page {{ page() }} of {{ pages() }}.</p>
              <div class="marketplace-actions">
                <button type="button" (click)="findProducts(page() - 1)" [disabled]="page() <= 1">
                  Previous products</button
                ><button
                  type="button"
                  (click)="findProducts(page() + 1)"
                  [disabled]="page() >= pages()"
                >
                  Next products
                </button>
              </div>
              @if (product(); as selected) {
                <p>
                  <strong>{{ selected.name }}</strong> · {{ selected.brand_name }} ·
                  {{ selected.status }} · <span class="reference">{{ selected.id }}</span>
                </p>
                <label for="opening-variant">Product variant</label
                ><select
                  id="opening-variant"
                  name="variant"
                  [(ngModel)]="variantId"
                  (ngModelChange)="chooseVariant()"
                >
                  <option value="">Product-level stock (no variant)</option>
                  @for (variant of variants(); track variant.id) {
                    <option [value]="variant.id">
                      {{ variant.title || variant.variant_key }} ·
                      {{ variant.sku || 'No variant SKU' }}
                    </option>
                  }
                </select>
                <p>
                  Choose a variant when these counted units belong to that specific variant. Do not
                  also count the same units as product-level stock.
                </p>
                <h3>Current canonical stock for this product</h3>
                @for (item of existing(); track item.id) {
                  <p>
                    {{ item.internal_sku }} · {{ item.location_code }}:
                    {{ item.on_hand_quantity }} on hand, {{ item.available_to_promise }} available
                    (version {{ item.version }}). Use an adjustment for this existing balance.
                  </p>
                } @empty {
                  <p>No canonical stock records exist for this product.</p>
                }
              }
              <h2>2. Record your counted units</h2>
              <div class="workspace-grid-form">
                <div>
                  <label for="opening-sku">Internal SKU</label
                  ><input
                    id="opening-sku"
                    name="sku"
                    [(ngModel)]="sku"
                    maxlength="100"
                    [attr.aria-invalid]="errors()['sku'] ? 'true' : null"
                    aria-describedby="sku-error"
                  /><span id="sku-error" class="marketplace-error">{{ errors()['sku'] }}</span>
                </div>
                <div>
                  <label for="opening-location">Location code</label
                  ><input
                    id="opening-location"
                    name="location"
                    [(ngModel)]="location"
                    maxlength="80"
                    [attr.aria-invalid]="errors()['location'] ? 'true' : null"
                    aria-describedby="location-help location-error"
                  /><small id="location-help">Use default unless you track a named location.</small
                  ><span id="location-error" class="marketplace-error">{{
                    errors()['location']
                  }}</span>
                </div>
                <div>
                  <label for="opening-unit">Unit</label
                  ><input
                    id="opening-unit"
                    name="unit"
                    [(ngModel)]="unit"
                    maxlength="24"
                    [attr.aria-invalid]="errors()['unit'] ? 'true' : null"
                    aria-describedby="unit-error"
                  /><span id="unit-error" class="marketplace-error">{{ errors()['unit'] }}</span>
                </div>
                <div>
                  <label for="opening-quantity">Opening quantity</label
                  ><input
                    id="opening-quantity"
                    name="quantity"
                    type="number"
                    [(ngModel)]="quantity"
                    min="0"
                    max="2000000000"
                    step="1"
                    [attr.aria-invalid]="errors()['quantity'] ? 'true' : null"
                    aria-describedby="quantity-help quantity-error"
                  /><small id="quantity-help"
                    >Whole counted units, 0–2,000,000,000. Enter zero only for a known zero
                    balance.</small
                  ><span id="quantity-error" class="marketplace-error">{{
                    errors()['quantity']
                  }}</span>
                </div>
                <div>
                  <label for="opening-threshold">Low-stock alert threshold</label
                  ><input
                    id="opening-threshold"
                    name="threshold"
                    type="number"
                    [(ngModel)]="threshold"
                    min="0"
                    max="2000000000"
                    step="1"
                    [attr.aria-invalid]="errors()['threshold'] ? 'true' : null"
                    aria-describedby="threshold-error"
                  /><span id="threshold-error" class="marketplace-error">{{
                    errors()['threshold']
                  }}</span>
                </div>
              </div>
              <div class="marketplace-actions">
                <button type="submit" [disabled]="busy()">Review opening stock</button
                ><a routerLink="/marketplaces/inventory" [queryParams]="returnFilters">Cancel</a>
              </div>
            </fieldset>
          </form>
        }
      }
    </section>
  `,
})
export class OpeningStockComponent {
  private readonly inventory = inject(MarketplaceService);
  private readonly catalog = inject(CatalogService);
  private readonly productService = inject(ProductService);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  readonly products = signal<ProductSummary[]>([]);
  readonly product = signal<ProductSummary | null>(null);
  readonly variants = signal<CatalogVariant[]>([]);
  readonly existing = signal<InventoryItem[]>([]);
  readonly review = signal<InventoryOpeningRequest | null>(null);
  readonly saved = signal<InventoryItem | null>(null);
  readonly opening = signal<InventoryMovement | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly uncertain = signal(false);
  readonly error = signal('');
  readonly notice = signal('');
  readonly errors = signal<Record<string, string>>({});
  readonly page = signal(1);
  readonly pages = signal(1);
  readonly returnFilters = {
    sku: this.route.snapshot.queryParamMap.get('sku') || null,
    low_stock: this.route.snapshot.queryParamMap.get('low_stock') === 'true' ? 'true' : null,
  };
  productId = '';
  variantId = '';
  search = '';
  sku = '';
  location = 'default';
  unit = 'each';
  quantity: number | null = null;
  threshold: number | null = 0;
  confirmed = false;
  private get storageKey(): string {
    return `vj-opening-${this.auth.user()?.id || 'unauthenticated'}`;
  }
  constructor() {
    void this.initialize();
  }
  private focus(selector: string): void {
    setTimeout(() => this.element.nativeElement.querySelector<HTMLElement>(selector)?.focus());
  }
  variantName(): string {
    const id = this.review()?.variant_id;
    if (!id) return 'Product-level stock';
    const variant = this.variants().find((v) => v.id === id);
    return variant?.title || variant?.variant_key || `Variant reference: ${id}`;
  }
  async findProducts(page = 1): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      const result = await this.productService.list({
        productType: 'physical',
        includeArchived: false,
        allBrands: true,
        search: this.search || undefined,
        page,
        pageSize: 20,
      });
      this.products.set(result.items);
      this.page.set(result.page);
      this.pages.set(Math.max(1, result.pages));
    } catch {
      this.error.set(
        'Product search could not be loaded. Retry Find products. No stock was changed.',
      );
    } finally {
      this.busy.set(false);
    }
  }
  private async initialize(): Promise<void> {
    try {
      const savedId = this.route.snapshot.queryParamMap.get('item_id');
      if (savedId) {
        await this.verify(savedId);
        return;
      }
      await this.findProducts();
      const raw = sessionStorage.getItem(this.storageKey);
      if (raw) {
        const value: unknown = JSON.parse(raw);
        if (
          value &&
          typeof value === 'object' &&
          'payload' in value &&
          storedRequest(value.payload)
        ) {
          this.review.set(value.payload);
          this.uncertain.set('pending' in value && value.pending === true);
          await this.choose(value.payload.product_id);
          this.notice.set(
            'Review restored for this owner and browser tab. Nothing is submitted automatically. Confirm again to continue.',
          );
        } else {
          sessionStorage.removeItem(this.storageKey);
        }
      }
    } catch {
      this.error.set(
        'The product or saved stock could not be loaded. Refresh, or return to inventory. No automatic stock change was made.',
      );
    } finally {
      this.loading.set(false);
    }
  }
  async choose(id: string): Promise<void> {
    this.productId = id;
    this.product.set(null);
    this.variants.set([]);
    this.existing.set([]);
    this.variantId = '';
    this.error.set('');
    if (!id) return;
    this.busy.set(true);
    try {
      const [detail, items] = await Promise.all([
        this.catalog.getProduct(id),
        this.inventory.canonicalInventory(),
      ]);
      if (this.productId !== id) return;
      if (detail.product.product_type !== 'physical' || detail.product.status === 'archived')
        throw new Error('INELIGIBLE');
      this.product.set(detail.product);
      this.variants.set(detail.variants.filter((v) => v.status !== 'archived'));
      this.existing.set(items.filter((i) => i.product_id === id));
      this.sku = detail.product.sku || '';
    } catch {
      this.error.set(
        'This product is no longer available or its current stock could not be loaded. Choose an available physical product and retry.',
      );
    } finally {
      if (this.productId === id) this.busy.set(false);
    }
  }
  chooseVariant(): void {
    this.sku =
      this.variants().find((v) => v.id === this.variantId)?.sku || this.product()?.sku || '';
  }
  async prepare(): Promise<void> {
    if (this.busy()) return;
    const errors: Record<string, string> = {};
    if (!this.product() || this.productId !== this.product()?.id)
      errors['product'] = 'Choose an available physical product.';
    for (const [key, value, max] of [
      ['sku', this.sku, 100],
      ['location', this.location, 80],
      ['unit', this.unit, 24],
    ] as const)
      if (!value.trim() || value.trim().length > max)
        errors[key] = `Enter 1–${max} non-blank characters.`;
    if (!wholeStock(this.quantity))
      errors['quantity'] = 'Enter a whole counted quantity from 0 to 2,000,000,000.';
    if (!wholeStock(this.threshold))
      errors['threshold'] = 'Enter a whole threshold from 0 to 2,000,000,000.';
    this.errors.set(errors);
    this.error.set('');
    if (Object.keys(errors).length) {
      this.focus('[aria-invalid="true"]');
      return;
    }
    this.busy.set(true);
    try {
      // Fresh canonical eligibility and stock read before the review, not cached UI state.
      const [detail, items] = await Promise.all([
        this.catalog.getProduct(this.productId),
        this.inventory.canonicalInventory(),
      ]);
      if (
        detail.product.product_type !== 'physical' ||
        detail.product.status === 'archived' ||
        (this.variantId &&
          !detail.variants.some((v) => v.id === this.variantId && v.status !== 'archived'))
      )
        throw new Error('PRODUCT_UNAVAILABLE');
      this.product.set(detail.product);
      this.variants.set(detail.variants.filter((v) => v.status !== 'archived'));
      this.existing.set(items.filter((i) => i.product_id === this.productId));
      if (
        items.some(
          (i) => i.internal_sku === this.sku.trim() && i.location_code === this.location.trim(),
        )
      )
        throw new Error('EXISTING');
      const payload: InventoryOpeningRequest = {
        product_id: this.productId,
        variant_id: this.variantId || null,
        internal_sku: this.sku.trim(),
        location_code: this.location.trim(),
        unit: this.unit.trim(),
        opening_quantity: Number(this.quantity),
        low_stock_threshold: Number(this.threshold),
        idempotency_key: `ui-opening-${crypto.randomUUID()}`,
      };
      this.persist(payload, false);
      this.review.set(payload);
      this.uncertain.set(false);
      this.confirmed = false;
      this.focus('#opening-review');
    } catch {
      this.error.set(
        'Review could not be prepared. An opening record may already exist for this SKU/location, the product may be unavailable, or tab storage may be blocked. Review existing stock; use an adjustment, not another opening balance.',
      );
      this.focus('#opening-error');
    } finally {
      this.busy.set(false);
    }
  }
  edit(): void {
    if (this.busy() || this.uncertain()) return;
    const p = this.review();
    if (!p) return;
    this.productId = p.product_id;
    this.variantId = p.variant_id || '';
    this.sku = p.internal_sku;
    this.location = p.location_code;
    this.unit = p.unit;
    this.quantity = p.opening_quantity;
    this.threshold = p.low_stock_threshold;
    sessionStorage.removeItem(this.storageKey);
    this.review.set(null);
    this.confirmed = false;
    this.focus('select[name="product"]');
  }
  private persist(payload: InventoryOpeningRequest, pending: boolean): void {
    sessionStorage.setItem(this.storageKey, JSON.stringify({ payload, pending }));
  }
  async submit(): Promise<void> {
    const payload = this.review();
    if (!payload || !this.confirmed || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    let accepted = false;
    try {
      this.persist(payload, true);
      this.uncertain.set(true);
      const row = await this.inventory.createInventoryItem(payload);
      accepted = true;
      await this.verify(row.id, payload);
      sessionStorage.removeItem(this.storageKey);
      this.uncertain.set(false);
      this.notice.set('');
      await this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { item_id: row.id },
        queryParamsHandling: 'merge',
        replaceUrl: true,
      });
      this.focus('#opening-success');
    } catch (error) {
      const definitive =
        !accepted &&
        error instanceof HttpErrorResponse &&
        [400, 404, 409, 422].includes(error.status);
      if (definitive) {
        try {
          this.persist(payload, false);
          this.uncertain.set(false);
        } catch {
          /* Preserve the pending identity if storage is unavailable. */
        }
      }
      this.error.set(
        definitive
          ? ProductService.errorMessage(error)
          : 'Save or verification was interrupted. The outcome is not confirmed. Check inventory or retry this identical request; do not start another opening balance.',
      );
      this.confirmed = false;
      this.focus('#opening-error');
    } finally {
      this.busy.set(false);
    }
  }
  private async verify(id: string, payload?: InventoryOpeningRequest): Promise<void> {
    const [items, movements] = await Promise.all([
      this.inventory.canonicalInventory(),
      this.inventory.inventoryLedger(id),
    ]);
    const item = items.find((i) => i.id === id);
    const opening = movements.find(
      (m) => m.movement_type === 'opening_balance' && m.actor_type === 'HUMAN',
    );
    if (
      !item ||
      !opening ||
      (payload &&
        (item.product_id !== payload.product_id ||
          item.variant_id !== payload.variant_id ||
          item.internal_sku !== payload.internal_sku ||
          item.location_code !== payload.location_code ||
          item.unit !== payload.unit ||
          item.low_stock_threshold !== payload.low_stock_threshold ||
          opening.quantity !== payload.opening_quantity))
    )
      throw new Error('OPENING_NOT_VERIFIED');
    const detail = await this.catalog.getProduct(item.product_id);
    this.product.set(detail.product);
    this.saved.set(item);
    this.opening.set(opening);
  }
}
