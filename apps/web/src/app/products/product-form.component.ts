import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import type { BrandSummary, CreateProductRequest, ProductType, WeightUnit } from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import { ProductService } from './product.service';

@Component({
  selector: 'app-product-form',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="page narrow">
      <header class="page-header">
        <div>
          <p class="eyebrow">Product Management</p>
          <h1>{{ editing() ? 'Edit product' : 'Create product' }}</h1>
        </div>
      </header>
      @if (loading()) {
        <p class="state">Loading product…</p>
      } @else if (!brands().length) {
        <div class="state">
          <h2>Create a brand first</h2>
          <a class="button" routerLink="/brands/new">Create brand</a>
        </div>
      } @else {
        <form class="product-form" [formGroup]="form" (ngSubmit)="save()">
          <fieldset>
            <legend>Basic information</legend>
            <label
              >Brand *<select formControlName="brand_id">
                @for (brand of brands(); track brand.id) {
                  <option [value]="brand.id">{{ brand.name }}</option>
                }
              </select></label
            >
            <label>Name *<input formControlName="name" maxlength="160" /></label>
            <label
              >Slug<input formControlName="slug" maxlength="160" placeholder="generated-from-name"
            /></label>
            <label
              >Product type *<select formControlName="product_type">
                <option value="physical">Physical</option>
                <option value="digital">Digital</option>
                <option value="service">Service</option>
                <option value="affiliate">Affiliate</option>
              </select></label
            >
            <label>Category<input formControlName="category" maxlength="120" /></label>
            <label>Tags<input formControlName="tags" placeholder="tag one, tag two" /></label>
            <label class="checkbox"
              ><input type="checkbox" formControlName="is_featured" /> Featured</label
            >
          </fieldset>
          <fieldset>
            <legend>Content</legend>
            <label
              >Short description<textarea
                formControlName="short_description"
                maxlength="500"
                rows="3"
              ></textarea>
            </label>
            <label
              >Description<textarea
                formControlName="description"
                maxlength="10000"
                rows="7"
              ></textarea>
            </label>
          </fieldset>
          <fieldset>
            <legend>Pricing</legend>
            <label
              >Price<input formControlName="price_amount" inputmode="decimal" placeholder="19.99"
            /></label>
            <label
              >Currency<input formControlName="price_currency" maxlength="3" placeholder="USD"
            /></label>
            <label
              >Compare-at price<input formControlName="compare_at_price_amount" inputmode="decimal"
            /></label>
            <label>Cost<input formControlName="cost_amount" inputmode="decimal" /></label>
            <label>Tax code<input formControlName="tax_code" maxlength="50" /></label>
          </fieldset>
          <fieldset>
            <legend>Identifiers</legend>
            <label>SKU<input formControlName="sku" maxlength="100" /></label>
            <label>Barcode<input formControlName="barcode" maxlength="100" /></label>
          </fieldset>
          <fieldset>
            <legend>Inventory</legend>
            <label class="checkbox"
              ><input type="checkbox" formControlName="inventory_tracking_enabled" /> Track
              inventory</label
            >
            <label
              >Quantity<input type="number" min="0" formControlName="inventory_quantity"
            /></label>
            <label
              >Low-stock threshold<input
                type="number"
                min="0"
                formControlName="low_stock_threshold"
            /></label>
          </fieldset>
          <fieldset>
            <legend>Shipping</legend>
            <label>Weight<input formControlName="weight_value" inputmode="decimal" /></label>
            <label
              >Weight unit<select formControlName="weight_unit">
                <option value="">None</option>
                <option value="g">g</option>
                <option value="kg">kg</option>
                <option value="oz">oz</option>
                <option value="lb">lb</option>
              </select></label
            >
          </fieldset>
          @if (form.controls.name.touched && form.controls.name.invalid) {
            <p class="error">A product name is required.</p>
          }
          @if (form.controls.price_amount.touched && form.controls.price_amount.invalid) {
            <p class="error">Use a non-negative decimal with at most two fractional digits.</p>
          }
          @if (
            form.controls.compare_at_price_amount.touched &&
            form.controls.compare_at_price_amount.invalid
          ) {
            <p class="error">Compare-at price must use a valid decimal format.</p>
          }
          @if (error()) {
            <p class="error" role="alert">{{ error() }}</p>
          }
          <div class="actions">
            <a class="button" [routerLink]="cancelUrl()">Cancel</a>
            <button class="button primary" type="submit" [disabled]="form.invalid || saving()">
              {{ saving() ? 'Saving…' : 'Save product' }}
            </button>
          </div>
        </form>
      }
    </section>
  `,
  styleUrl: './products.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProductFormComponent {
  private readonly fb = inject(FormBuilder);
  private readonly products = inject(ProductService);
  private readonly brandService = inject(BrandService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly id = this.route.snapshot.paramMap.get('id');
  readonly editing = signal(Boolean(this.id));
  readonly brands = signal<BrandSummary[]>([]);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal('');
  private readonly moneyPattern = /^(?:0|[1-9]\d{0,9})(?:\.\d{1,2})?$/;
  private readonly weightPattern = /^(?:0|[1-9]\d{0,8})(?:\.\d{1,3})?$/;
  readonly form = this.fb.nonNullable.group({
    brand_id: ['', Validators.required],
    name: ['', [Validators.required, Validators.maxLength(160)]],
    slug: ['', [Validators.pattern(/^[a-z0-9]+(?:-[a-z0-9]+)*$/), Validators.maxLength(160)]],
    sku: ['', Validators.maxLength(100)],
    product_type: new FormControl<ProductType>('physical', { nonNullable: true }),
    category: ['', Validators.maxLength(120)],
    tags: [''],
    is_featured: [false],
    short_description: ['', Validators.maxLength(500)],
    description: ['', Validators.maxLength(10000)],
    price_amount: ['', Validators.pattern(this.moneyPattern)],
    price_currency: ['USD', Validators.pattern(/^[A-Za-z]{3}$/)],
    compare_at_price_amount: ['', Validators.pattern(this.moneyPattern)],
    cost_amount: ['', Validators.pattern(this.moneyPattern)],
    tax_code: ['', Validators.maxLength(50)],
    barcode: ['', Validators.maxLength(100)],
    inventory_tracking_enabled: [false],
    inventory_quantity: [0, [Validators.min(0), Validators.max(2_000_000_000)]],
    low_stock_threshold: [0, [Validators.min(0), Validators.max(2_000_000_000)]],
    weight_value: ['', Validators.pattern(this.weightPattern)],
    weight_unit: new FormControl<WeightUnit | ''>('', { nonNullable: true }),
  });

  constructor() {
    void this.initialize();
  }

  cancelUrl(): string {
    return this.id ? `/products/${this.id}` : '/products';
  }

  private async initialize(): Promise<void> {
    try {
      const brandItems = (await this.brandService.list({ includeArchived: false, pageSize: 100 }))
        .items;
      this.brands.set(brandItems);
      if (this.id) {
        const product = await this.products.get(this.id);
        this.form.patchValue({
          brand_id: product.brand_id,
          name: product.name,
          slug: product.slug,
          sku: product.sku ?? '',
          product_type: product.product_type,
          category: product.category ?? '',
          tags: product.tags.join(', '),
          is_featured: product.is_featured,
          short_description: product.short_description ?? '',
          description: product.description ?? '',
          price_amount: product.price_amount ?? '',
          price_currency: product.price_currency ?? '',
          compare_at_price_amount: product.compare_at_price_amount ?? '',
          cost_amount: product.cost_amount ?? '',
          tax_code: product.tax_code ?? '',
          barcode: product.barcode ?? '',
          inventory_tracking_enabled: product.inventory_tracking_enabled,
          inventory_quantity: product.inventory_quantity,
          low_stock_threshold: product.low_stock_threshold,
          weight_value: product.weight_value ?? '',
          weight_unit: product.weight_unit ?? '',
        });
      } else {
        this.form.controls.brand_id.setValue(
          this.brandService.activeBrand()?.id ?? brandItems[0]?.id ?? '',
        );
      }
    } catch (error) {
      this.error.set(ProductService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }

  async save(): Promise<void> {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.error.set('');
    const value = this.form.getRawValue();
    const optional = (input: string): string | null => input.trim() || null;
    const payload: CreateProductRequest = {
      brand_id: value.brand_id,
      name: value.name.trim(),
      slug: optional(value.slug),
      sku: optional(value.sku),
      product_type: value.product_type,
      category: optional(value.category),
      tags: value.tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean),
      is_featured: value.is_featured,
      short_description: optional(value.short_description),
      description: optional(value.description),
      price_amount: optional(value.price_amount),
      price_currency: optional(value.price_currency)?.toUpperCase() ?? null,
      compare_at_price_amount: optional(value.compare_at_price_amount),
      cost_amount: optional(value.cost_amount),
      tax_code: optional(value.tax_code),
      barcode: optional(value.barcode),
      inventory_tracking_enabled: value.inventory_tracking_enabled,
      inventory_quantity: value.inventory_quantity,
      low_stock_threshold: value.low_stock_threshold,
      weight_value: optional(value.weight_value),
      weight_unit: value.weight_unit || null,
    };
    try {
      const product = this.id
        ? await this.products.update(this.id, payload)
        : await this.products.create(payload);
      await this.router.navigate(['/products', product.id]);
    } catch (error) {
      this.error.set(ProductService.errorMessage(error));
    } finally {
      this.saving.set(false);
    }
  }
}
