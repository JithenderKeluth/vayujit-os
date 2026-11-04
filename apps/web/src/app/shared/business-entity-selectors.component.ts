import { CommonModule } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnInit,
  Output,
  SimpleChanges,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import type { AIStudioArtifact, BrandSummary, ProductSummary } from '@vayujit/shared';
import { environment } from '../../environments/environment';
import { BrandService } from '../brands/brand.service';
import { ProductService } from '../products/product.service';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from './state-components';

export type BusinessMediaOption = {
  media_id: string;
  source_type: string;
  operation: string | null;
  status: string;
  channel: string | null;
  width: number;
  height: number;
  mime: string | null;
  approval: string;
  generated_at: string | null;
};

@Component({
  selector: 'app-business-entity-selectors',
  standalone: true,
  imports: [
    CommonModule,
    EmptyStateComponent,
    ErrorStateComponent,
    FormsModule,
    RouterLink,
    LoadingStateComponent,
  ],
  template: `
    <section class="business-selectors" aria-label="Business context selectors">
      @if (loading()) {
        <app-loading-state message="Loading available business context..." />
      }
      @if (error()) {
        <app-error-state
          title="Business context is unavailable"
          [message]="error()"
          retryLabel="Retry business context"
          (retry)="loadContext()"
        />
      }
      @if (showProduct && !multiProduct) {
        <label>
          {{ productLabel }}
          <select
            [attr.aria-label]="productLabel"
            [value]="productId"
            (change)="selectProduct($any($event.target).value)"
            [disabled]="loading()"
          >
            <option value="">Select a Product</option>
            @for (product of products(); track product.id) {
              <option [value]="product.id">
                {{ product.name }}{{ product.sku ? ' - SKU ' + product.sku : ''
                }}{{ product.category ? ' - ' + product.category : '' }}
              </option>
            }
          </select>
        </label>
      }
      @if (showProduct && multiProduct) {
        <fieldset class="product-selector">
          <legend>{{ productLabel }} ({{ productIds.length }} selected)</legend>
          @for (product of products(); track product.id) {
            <label
              ><input
                type="checkbox"
                [checked]="productIds.includes(product.id)"
                (change)="toggleProduct(product.id)"
              />
              {{ product.name }}{{ product.sku ? ' - SKU ' + product.sku : '' }}</label
            >
          }
        </fieldset>
      }
      @if (showProduct && !products().length && !loading() && !error()) {
        <app-empty-state
          title="No active products available"
          message="This workflow lists active products only. Draft and archived products are not eligible. Review your existing Catalog and product status before creating another product."
          ><a routerLink="/catalog">Review Catalog products</a></app-empty-state
        >
      }
      @if (showBrand) {
        <label>
          {{ brandLabel }}
          <select
            [attr.aria-label]="brandLabel"
            [value]="brandId"
            (change)="selectBrand($any($event.target).value)"
            [disabled]="loading()"
          >
            <option value="">Select a Brand</option>
            @for (brand of brands(); track brand.id) {
              <option [value]="brand.id">{{ brand.name }}</option>
            }
          </select>
        </label>
        @if (!brands().length && !loading() && !error()) {
          <app-empty-state
            title="No brands available"
            message="Create a Brand before continuing this workflow."
          />
        }
      }
      @if (showArtifact) {
        <label>
          {{ artifactLabel }}
          <select
            [attr.aria-label]="artifactLabel"
            [value]="artifactId"
            (change)="selectArtifact($any($event.target).value)"
            [disabled]="artifactLoading() || !productId"
          >
            <option value="">
              {{ productId ? 'Select eligible content' : 'Select a Product first' }}
            </option>
            @for (artifact of artifacts(); track artifact.id) {
              <option [value]="artifact.id">
                {{ artifact.content_type }} - {{ artifact.channel }} - v{{
                  artifact.version_number
                }}
                - {{ artifact.status }}
              </option>
            }
          </select>
        </label>
        @if (productId && !artifactLoading() && !artifacts().length) {
          <app-empty-state
            title="No approved content available"
            message="Generate and approve eligible content before continuing."
          />
        }
      }
      @if (showMedia) {
        <fieldset class="media-selector">
          <legend>{{ mediaLabel }}</legend>
          @if (!productId) {
            <p>Select a Product first.</p>
          }
          @if (productId && mediaLoading()) {
            <app-loading-state message="Loading Product media..." />
          }
          @if (productId && !mediaLoading() && !media().length) {
            <app-empty-state
              title="No media available for this Product"
              message="Add or generate media before continuing."
            />
          }
          @for (item of media(); track item.media_id) {
            <label>
              <input
                type="checkbox"
                [checked]="mediaIds.includes(item.media_id)"
                (change)="toggleMedia(item.media_id)"
              />
              {{ item.operation || 'Product media' }} - {{ item.source_type }} - {{ item.status }}
              @if (item.width && item.height) {
                ({{ item.width }}x{{ item.height }})
              }
            </label>
          }
        </fieldset>
      }
    </section>
  `,
  styles: [
    `
      .business-selectors {
        display: grid;
        gap: 0.75rem;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        align-items: start;
        min-width: 0;
      }
      :host,
      .business-selectors > *,
      label {
        min-width: 0;
        overflow-wrap: anywhere;
      }
      :host {
        display: block;
      }
      .business-selectors label,
      .media-selector,
      .product-selector {
        display: grid;
        gap: 0.35rem;
      }
      .business-selectors select {
        min-height: 2.5rem;
        width: 100%;
      }
      .media-selector {
        grid-column: 1 / -1;
        border: 1px solid #c8d9dc;
        border-radius: 0.5rem;
        padding: 0.75rem;
      }
      .media-selector label {
        display: block;
        margin: 0.35rem 0;
      }
      @media (max-width: 640px) {
        .business-selectors {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BusinessEntitySelectorsComponent implements OnInit, OnChanges {
  private readonly http = inject(HttpClient);
  private readonly productsService = inject(ProductService);
  private readonly brandsService = inject(BrandService);
  @Input() productId = '';
  @Output() productIdChange = new EventEmitter<string>();
  @Input() brandId = '';
  @Output() brandIdChange = new EventEmitter<string>();
  @Input() artifactId = '';
  @Output() artifactIdChange = new EventEmitter<string>();
  @Input() mediaIds: string[] = [];
  @Output() mediaIdsChange = new EventEmitter<string[]>();
  @Input() showProduct = true;
  @Input() multiProduct = false;
  @Input() productIds: string[] = [];
  @Output() productIdsChange = new EventEmitter<string[]>();
  @Input() showBrand = false;
  @Input() showArtifact = false;
  @Input() showMedia = false;
  @Input() approvedOnly = false;
  @Input() productLabel = 'Product';
  @Input() brandLabel = 'Brand';
  @Input() artifactLabel = 'Approved content';
  @Input() mediaLabel = 'Source media';
  readonly products = signal<ProductSummary[]>([]);
  readonly brands = signal<BrandSummary[]>([]);
  readonly artifacts = signal<AIStudioArtifact[]>([]);
  readonly media = signal<BusinessMediaOption[]>([]);
  readonly loading = signal(false);
  readonly artifactLoading = signal(false);
  readonly mediaLoading = signal(false);
  readonly error = signal('');
  private contextRequest = 0;
  private requestedBrand = '';

  ngOnInit(): void {
    void this.loadContext();
  }
  ngOnChanges(changes: SimpleChanges): void {
    if (
      changes['brandId'] &&
      !changes['brandId'].firstChange &&
      this.brandId !== this.requestedBrand
    ) {
      if (!changes['productId']) {
        this.productId = '';
        this.productIdChange.emit('');
      }
      void this.loadContext();
    }
    if (
      changes['productId'] &&
      !changes['productId'].firstChange &&
      (this.showArtifact || this.showMedia)
    )
      void this.loadProductDependents();
  }
  async loadContext(): Promise<void> {
    const request = ++this.contextRequest;
    this.requestedBrand = this.brandId;
    this.loading.set(true);
    this.error.set('');
    this.products.set([]);
    this.brands.set([]);
    try {
      const tasks: Promise<unknown>[] = [];
      if (this.showProduct)
        tasks.push(
          this.productsService
            .list({
              status: 'active',
              pageSize: 50,
              ...(this.brandId ? { brandId: this.brandId } : {}),
            })
            .then((page) => {
              if (request === this.contextRequest) this.products.set(page.items);
            }),
        );
      if (this.showBrand)
        tasks.push(
          this.brandsService.list({ status: 'active', pageSize: 50 }).then((page) => {
            if (request === this.contextRequest) this.brands.set(page.items);
          }),
        );
      await Promise.all(tasks);
      if (request !== this.contextRequest) return;
      await this.loadProductDependents();
    } catch {
      if (request === this.contextRequest)
        this.error.set('Unable to load available Products, Brands, or content.');
    } finally {
      if (request === this.contextRequest) this.loading.set(false);
    }
  }
  async loadProductDependents(): Promise<void> {
    if (!this.productId) {
      this.artifacts.set([]);
      this.media.set([]);
      return;
    }
    if (this.showArtifact) {
      this.artifactLoading.set(true);
      try {
        let params = new HttpParams().set('product_id', this.productId);
        if (this.approvedOnly) params = params.set('status', 'approved');
        const result = await firstValueFrom(
          this.http.get<AIStudioArtifact[]>(`${environment.apiUrl}/ai/studio/artifacts`, {
            params,
            withCredentials: true,
          }),
        );
        this.artifacts.set(result);
      } catch {
        this.error.set('Unable to load eligible content for this Product.');
      } finally {
        this.artifactLoading.set(false);
      }
    }
    if (this.showMedia) {
      this.mediaLoading.set(true);
      try {
        const result = await firstValueFrom(
          this.http.get<BusinessMediaOption[]>(
            `${environment.apiUrl}/ai/images/products/${this.productId}/media`,
            { withCredentials: true },
          ),
        );
        this.media.set(
          result.filter((item) => item.status === 'ready' || item.approval === 'approved'),
        );
      } catch {
        this.error.set('Unable to load media for this Product.');
      } finally {
        this.mediaLoading.set(false);
      }
    }
  }
  selectProduct(value: string): void {
    this.productId = value;
    this.productIdChange.emit(value);
    void this.loadProductDependents();
  }
  toggleProduct(value: string): void {
    const next = this.productIds.includes(value)
      ? this.productIds.filter((item) => item !== value)
      : [...this.productIds, value].slice(0, 50);
    this.productIds = next;
    this.productIdsChange.emit(next);
  }
  selectBrand(value: string): void {
    if (value === this.brandId) return;
    this.brandId = value;
    this.productId = '';
    this.productIds = [];
    this.artifactId = '';
    this.mediaIds = [];
    this.artifacts.set([]);
    this.media.set([]);
    this.productIdChange.emit('');
    this.productIdsChange.emit([]);
    this.artifactIdChange.emit('');
    this.mediaIdsChange.emit([]);
    this.brandIdChange.emit(value);
    void this.loadContext();
  }
  selectArtifact(value: string): void {
    this.artifactId = value;
    this.artifactIdChange.emit(value);
  }
  toggleMedia(value: string): void {
    const next = this.mediaIds.includes(value)
      ? this.mediaIds.filter((item) => item !== value)
      : [...this.mediaIds, value];
    this.mediaIds = next;
    this.mediaIdsChange.emit(next);
  }
}
