import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import type {
  AIArtifactDetails,
  AIHistoryItem,
  BrandSummary,
  ProductSummary,
  PublishingDestinationSummary,
  MediaAsset,
  PublishingPreview,
} from '@vayujit/shared';
import { AIService } from '../ai/ai.service';
import { BrandService } from '../brands/brand.service';
import { ProductService } from '../products/product.service';
import { PublicationPreviewComponent } from './publication-preview.component';
import { PublishingService } from './publishing.service';
import { OperationsService } from '../operations/operations.service';
import { MediaService } from '../media/media.service';

@Component({
  selector: 'app-publish-new',
  imports: [FormsModule, RouterLink, PublicationPreviewComponent],
  template: ` <section class="pub-page">
    <header>
      <h1>Publish approved content</h1>
      <p class="pub-muted">
        Choose business records by name and review exactly what the local mock connector will
        receive.
      </p>
    </header>
    @if (loading()) {
      <p role="status">Loading approved content and destinations…</p>
    }
    @if (error()) {
      <p class="pub-error" role="alert">{{ error() }}</p>
    }
    <form class="pub-card pub-form" (ngSubmit)="publish()">
      <label
        >1. Brand
        <select name="brand" [(ngModel)]="brandId" (ngModelChange)="brandChanged()">
          <option value="">Select Brand</option>
          @for (brand of brands(); track brand.id) {
            <option [value]="brand.id">{{ brand.name }}</option>
          }
        </select></label
      ><label
        >2. Product
        <select name="product" [(ngModel)]="productId" (ngModelChange)="productChanged()">
          <option value="">Select Product</option>
          @for (product of eligibleProducts(); track product.id) {
            <option [value]="product.id">{{ product.name }}</option>
          }
        </select></label
      ><label
        >3. Approved artifact
        <select name="artifact" [(ngModel)]="artifactId" (ngModelChange)="artifactChanged()">
          <option value="">Select approved version</option>
          @for (item of eligibleArtifacts(); track item.artifact_id) {
            <option [value]="item.artifact_id">
              Version {{ item.version_number }} · {{ item.template_name }} v{{
                item.template_version
              }}
              · approved
            </option>
          }
        </select></label
      ><label
        >4. Action
        <select name="action" [(ngModel)]="action" (ngModelChange)="refreshPreview()">
          <option value="create_draft">Create draft</option>
          <option value="publish">Publish</option>
          <option value="update">Update existing WordPress post</option>
        </select></label
      ><label
        >5. Compatible destination
        <select name="destination" [(ngModel)]="destinationId" (ngModelChange)="refreshPreview()">
          <option value="">Select destination</option>
          @for (item of compatibleDestinations(); track item.id) {
            <option [value]="item.id">
              {{ item.name }} · {{ item.brand_name || 'All Brands' }}
            </option>
          }
        </select></label
      >
      @if (selectedDestination()?.connector_key === 'wordpress') {
        <label
          >6. Featured image
          <select
            name="featuredMedia"
            [(ngModel)]="featuredMediaId"
            (ngModelChange)="refreshPreview()"
          >
            <option value="">No featured image</option>
            @for (media of mediaItems(); track media.id) {
              <option [value]="media.id">
                {{ media.safe_filename }} · {{ media.width }}×{{ media.height }}
              </option>
            }
          </select>
        </label>
        <a routerLink="/media/upload">Upload a new image</a>
      }
      @if (productId && !eligibleArtifacts().length) {
        <div class="pub-empty">
          <p>No approved artifact is eligible for this Product.</p>
          <a routerLink="/ai/generate">Generate content</a>
        </div>
      }
      @if (artifactId && !compatibleDestinations().length) {
        <div class="pub-empty">
          <p>No active destination is compatible with this Brand.</p>
          <a routerLink="/publishing/destinations/new">Create destination</a>
        </div>
      }
      <app-publication-preview
        [artifact]="selectedArtifact()"
        [product]="selectedProduct()"
        [destination]="selectedDestination()"
      />
      @if (preview(); as mapped) {
        <article class="pub-card">
          <h2>WordPress mapped preview</h2>
          <dl>
            <dt>Title</dt>
            <dd>{{ mapped.title }}</dd>
            <dt>Slug</dt>
            <dd>{{ mapped.slug }}</dd>
            <dt>Status</dt>
            <dd>{{ mapped.post_status }}</dd>
            <dt>Excerpt</dt>
            <dd>{{ mapped.excerpt }}</dd>
            <dt>Categories</dt>
            <dd>{{ mapped.category_ids.join(', ') || 'None' }}</dd>
            <dt>Tags</dt>
            <dd>{{ mapped.tag_ids.join(', ') || 'None' }}</dd>
            <dt>Author</dt>
            <dd>{{ mapped.author_id || 'WordPress default' }}</dd>
          </dl>
          <h3>Original generated text</h3>
          <pre>{{ mapped.original_text }}</pre>
          <h3>Sanitized WordPress output</h3>
          <pre>{{ mapped.sanitized_body }}</pre>
          <ul>
            @for (change of mapped.sanitization_changes; track change.kind) {
              <li>
                <strong>{{ change.kind }}</strong
                >: {{ change.message }}
              </li>
            }
          </ul>
        </article>
      }
      @if (selectedArtifact() && selectedDestination()) {
        <label
          ><input type="checkbox" name="confirmed" [(ngModel)]="confirmed" /> I confirm this
          intentional publishing action.</label
        ><button [disabled]="busy() || !confirmed">
          {{ busy() ? 'Publishing…' : 'Run publishing action' }}
        </button>
      }
    </form>
  </section>`,
  styleUrl: './publishing.css',
})
export class PublishNewComponent implements OnInit {
  private readonly publishing = inject(PublishingService);
  private readonly brandApi = inject(BrandService);
  private readonly productsApi = inject(ProductService);
  private readonly ai = inject(AIService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly operations = inject(OperationsService);
  private readonly mediaApi = inject(MediaService);
  private preferredDestinationId = '';
  readonly brands = signal<BrandSummary[]>([]);
  readonly products = signal<ProductSummary[]>([]);
  readonly artifacts = signal<AIHistoryItem[]>([]);
  readonly artifactDetails = signal<AIArtifactDetails | null>(null);
  readonly destinations = signal<PublishingDestinationSummary[]>([]);
  readonly mediaItems = signal<MediaAsset[]>([]);
  readonly preview = signal<PublishingPreview | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  brandId = '';
  productId = '';
  artifactId = '';
  destinationId = '';
  featuredMediaId = '';
  confirmed = false;
  action: 'create_draft' | 'publish' | 'update' = 'publish';
  private idempotencyKey = '';
  readonly eligibleProducts = computed(() =>
    this.products().filter((item) => item.brand_id === this.brandId && item.status !== 'archived'),
  );
  readonly eligibleArtifacts = computed(() =>
    this.artifacts().filter(
      (item) =>
        item.product_id === this.productId &&
        item.artifact_status === 'approved' &&
        item.artifact_id,
    ),
  );
  readonly compatibleDestinations = computed(() =>
    this.destinations().filter(
      (item) => item.status === 'active' && (!item.brand_id || item.brand_id === this.brandId),
    ),
  );
  readonly selectedProduct = computed(
    () => this.products().find((item) => item.id === this.productId) ?? null,
  );
  readonly selectedDestination = computed(
    () => this.destinations().find((item) => item.id === this.destinationId) ?? null,
  );
  readonly selectedArtifact = this.artifactDetails;
  ngOnInit(): void {
    void this.load();
  }
  private async load() {
    try {
      const [brands, active, products, artifacts, destinations, settings, media] =
        await Promise.all([
          this.brandApi.list({ pageSize: 100 }),
          this.brandApi.loadActive(),
          this.productsApi.list({ allBrands: true, pageSize: 100 }),
          this.ai.history({ artifactStatus: 'approved', pageSize: 100 }),
          this.publishing.destinations({ status: 'active', pageSize: 100 }),
          this.operations.settings(),
          this.mediaApi.list({ pageSize: 100 }),
        ]);
      this.brands.set(brands.items);
      this.products.set(products.items);
      this.artifacts.set(artifacts.items);
      this.destinations.set(destinations.items);
      this.mediaItems.set(media.items);
      this.brandId = active?.id ?? '';
      this.preferredDestinationId =
        this.route.snapshot.queryParamMap.get('destination') ??
        settings.preferences.default_publishing_destination_id ??
        '';
      this.applyPreferredDestination();
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  brandChanged() {
    this.productId = '';
    this.artifactId = '';
    this.artifactDetails.set(null);
    this.applyPreferredDestination();
    this.confirmed = false;
    this.idempotencyKey = '';
  }
  private applyPreferredDestination(): void {
    const preferred = this.destinations().find(
      (item) =>
        item.id === this.preferredDestinationId &&
        item.status === 'active' &&
        (!item.brand_id || item.brand_id === this.brandId),
    );
    this.destinationId = preferred?.id ?? '';
  }
  productChanged() {
    this.artifactId = '';
    this.artifactDetails.set(null);
    this.confirmed = false;
    this.idempotencyKey = '';
  }
  async artifactChanged() {
    this.confirmed = false;
    this.idempotencyKey = '';
    this.artifactDetails.set(this.artifactId ? await this.ai.artifact(this.artifactId) : null);
    await this.refreshPreview();
  }
  async refreshPreview() {
    this.preview.set(null);
    if (
      !this.artifactId ||
      !this.destinationId ||
      this.selectedDestination()?.connector_key !== 'wordpress'
    )
      return;
    try {
      this.preview.set(
        await this.publishing.preview({
          artifact_id: this.artifactId,
          destination_id: this.destinationId,
          action: this.action,
          featured_media_id: this.featuredMediaId || null,
        }),
      );
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    }
  }
  async publish() {
    if (!this.artifactId || !this.destinationId || !this.confirmed || this.busy()) return;
    if (!confirm(`Run ${this.action} for this approved content?`)) return;
    this.busy.set(true);
    this.error.set('');
    this.idempotencyKey ||= crypto.randomUUID();
    try {
      const result = await this.publishing.publish({
        artifact_id: this.artifactId,
        destination_id: this.destinationId,
        idempotency_key: this.idempotencyKey,
        action: this.action,
        featured_media_id: this.featuredMediaId || null,
      });
      await this.router.navigate(['/publishing/executions', result.id]);
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}
