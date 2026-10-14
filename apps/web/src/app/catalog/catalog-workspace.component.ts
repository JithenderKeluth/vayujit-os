import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type {
  CatalogChannel,
  CatalogEconomics,
  CatalogListingDraft,
  CatalogProductImage,
  CatalogProductDetails,
  CatalogReadiness,
  CatalogVariant,
  PaginatedProductResponse,
} from '@vayujit/shared';
import { PageHeaderComponent } from '../shared/page-header.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
  BlockedStateComponent,
} from '../shared/state-components';
import { CatalogService } from './catalog.service';
import { ProductService } from '../products/product.service';
import { environment } from '../../environments/environment';

interface DraftEditState {
  title: string;
  description: string;
  category: string;
  imageRef: string;
  intendedPrice: string;
  currency: string;
  complianceJson: string;
}

interface MediaAssetOption {
  id: string;
  original_filename: string;
  preview_url: string;
  mime_type: string;
  status: string;
}

interface VariantEditState {
  title: string;
}

@Component({
  selector: 'app-catalog-workspace',
  standalone: true,
  imports: [
    BlockedStateComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    FormsModule,
    LoadingStateComponent,
    PageHeaderComponent,
    RouterLink,
  ],
  template: `
    <main class="page catalog-page">
      @if (selectedId) {
        <a class="back-link" routerLink="/catalog">← Back to Seller Catalog</a>
        @if (detailLoading()) {
          <app-loading-state message="Loading catalog context..." />
        } @else if (error()) {
          <app-error-state
            title="Catalog context is unavailable"
            [message]="error()"
            retryLabel="Retry"
            (retry)="loadDetail()"
          />
        } @else if (detail()) {
          <app-page-header
            eyebrow="Seller Catalog / Product master"
            [title]="detail()!.product.name"
            description="Prepare seller-owned product data and channel drafts. Nothing is published from this workspace."
          >
            <div page-header-actions>
              <a class="button" [routerLink]="['/products', detail()!.product.id]">Product record</a>
              <a class="button" [routerLink]="['/products', detail()!.product.id, 'edit']">Edit product</a>
            </div>
          </app-page-header>

          <section class="trust-banner" aria-label="Catalog safety boundary">
            <strong>Preparation only</strong>
            <span>Drafts are owner-scoped, require HUMAN review, and have no marketplace or supplier side effects.</span>
          </section>

          <section class="card context-card" aria-labelledby="identity-title">
            <div class="section-heading"><div><p class="eyebrow">Canonical identity</p><h2 id="identity-title">Product context</h2></div><span class="badge">{{ detail()!.product.status }}</span></div>
            <dl class="facts">
              <div><dt>Brand</dt><dd>{{ detail()!.product.brand_name }}</dd></div>
              <div><dt>SKU</dt><dd>{{ detail()!.product.sku || 'Not assigned' }}</dd></div>
              <div><dt>Category</dt><dd>{{ detail()!.product.category || 'Not recorded' }}</dd></div>
              <div><dt>Lineage</dt><dd>{{ detail()!.lineage?.source_kind || 'Manual catalog product' }}</dd></div>
            </dl>
            @if (detail()!.lineage) {
              <p class="muted">Source: {{ detail()!.lineage!.provenance_json['source'] || 'Product Opportunity' }}. Claims remain subject to seller review.</p>
            }
          </section>

          <section class="card" aria-labelledby="images-title">
            <div class="section-heading"><div><p class="eyebrow">Secure assets</p><h2 id="images-title">Product images</h2></div><span class="badge">Owner-scoped</span></div>
            <p class="muted">Select ready images from your private Media Library. Preview URLs require your authenticated session and never fetch remote URLs.</p>
            @if (imagesLoading()) { <app-loading-state message="Loading product images..." /> }
            @if (!imagesLoading()) {
              <div class="asset-picker">
                <label>Choose a ready media asset
                  <select [value]="selectedMediaId()" (change)="selectMedia($event)">
                    <option value="">Select an image…</option>
                    @for (media of mediaAssets(); track media.id) { <option [value]="media.id">{{ media.original_filename }}</option> }
                  </select>
                </label>
                <label>Alt text (recommended)<input [value]="newImageAlt()" (input)="newImageAlt.set($any($event.target).value)" maxlength="500" placeholder="Describe the product image" /></label>
                <label class="checkbox"><input type="checkbox" [checked]="newImagePrimary()" (change)="newImagePrimary.set($any($event.target).checked)" /> Make primary</label>
                <button class="button primary" type="button" [disabled]="!selectedMediaId() || imageSaving()" (click)="attachImage()">{{ imageSaving() ? 'Saving…' : 'Add image' }}</button>
              </div>
              @if (!images().length) { <p class="muted">No product images selected yet. Add a ready asset before preparing a channel draft.</p> }
              <div class="image-grid">
                @for (image of images(); track image.id) {
                  <article class="image-card" [class.primary-image]="image.is_primary">
                    <img [src]="mediaPreview(image.preview_url)" [alt]="image.alt_text || 'Product image'" loading="lazy" />
                    <div><strong>{{ image.is_primary ? 'Primary image' : 'Gallery image' }}</strong><span class="muted">{{ image.width }}×{{ image.height }} · {{ image.mime_type }}</span></div>
                    <label>Alt text<input [name]="image.id + '-alt'" [value]="image.alt_text || ''" (change)="updateImageAlt(image, $event)" maxlength="500" /></label>
                    <div class="actions"><button class="button" type="button" (click)="setPrimary(image)" [disabled]="image.is_primary">Set primary</button><button class="button danger" type="button" (click)="removeImage(image)">Remove</button></div>
                  </article>
                }
              </div>
            }
          </section>

          <section class="card" aria-labelledby="economics-title">
            <div class="section-heading"><div><p class="eyebrow">Canonical commercial context</p><h2 id="economics-title">Economics readiness</h2></div><span class="badge">No invented values</span></div>
            @if (economicsLoading()) { <app-loading-state message="Loading canonical economics..." /> }
            @else if (economics() && !economics()!.available) {
              <app-blocked-state title="Economics are not available yet" [reason]="economics()!.reason || 'Create a canonical sourcing economics context from the selected opportunity before making commercial decisions.'" />
              <a class="button" [routerLink]="['/intelligence/product-opportunities']">Review opportunity economics</a>
            } @else if (economics()?.projection) {
              <p class="success">Canonical economics are available for review. Values remain evidence-backed and may be partial.</p>
              <dl class="facts compact"><div><dt>Status</dt><dd>{{ economics()!.projection!['status'] || 'UNKNOWN' }}</dd></div><div><dt>Readiness</dt><dd>{{ economics()!.projection!['readiness'] || 'UNKNOWN' }}</dd></div><div><dt>Currency</dt><dd>{{ economics()!.projection!['currency'] || economics()!.projection!['reporting_currency'] || 'UNKNOWN' }}</dd></div></dl>
            } @else { <p class="muted">Canonical economics are unavailable for this product context.</p> }
          </section>

          <section class="card" aria-labelledby="agent-title">
            <div class="section-heading"><div><p class="eyebrow">Guided research</p><h2 id="agent-title">Business Agent guidance</h2></div><span class="badge">HUMAN review</span></div>
            <p class="muted">Product claims, suggestions, and supplier decisions must come from the canonical Business Agent and remain subject to your review. Catalog does not invent AI recommendations.</p>
            <a class="button" routerLink="/intelligence/business-agent">Open Business Agent</a>
          </section>

          @if (readiness()) {
            <section class="card readiness-card" aria-labelledby="readiness-title">
              <div class="section-heading"><div><p class="eyebrow">Readiness</p><h2 id="readiness-title">{{ readiness()!.readiness === 'BLOCKED' ? 'More information is required' : 'Ready for future submission' }}</h2></div><span class="badge" [class.ready]="readiness()!.readiness !== 'BLOCKED'">{{ readiness()!.readiness }}</span></div>
              @if (readiness()!.blockers.length) {
                <app-blocked-state title="Resolve these blockers before approval" [reason]="readiness()!.blockers.join(' · ')" />
              } @else {
                <p class="success">All current draft checks pass. HUMAN approval is still required before any future submission.</p>
              }
              <ol class="next-actions"><li>Complete the channel draft.</li><li>Review claims, images, and compliance details.</li><li>Approve explicitly as HUMAN when ready.</li></ol>
              <p class="muted">External publication: disabled in PR-SOS-01.</p>
            </section>
          }

          <section class="card" aria-labelledby="drafts-title">
            <div class="section-heading"><div><p class="eyebrow">Channel preparation</p><h2 id="drafts-title">Listing drafts</h2></div></div>
            <p class="muted">Create one seller-authored draft per channel. Drafts never create remote listings.</p>
            <div class="channel-grid">
              @for (channel of channels; track channel) {
                @let draft = draftFor(channel);
                <article class="channel-card">
                  <div class="channel-header"><h3>{{ channelLabel(channel) }}</h3><span class="badge">{{ draft?.status || 'not started' }}</span></div>
                  @if (draft) {
                    <p>{{ draft.title || 'Untitled draft' }}</p>
                    <form class="draft-form" (ngSubmit)="saveDraft(draft)">
                      <label>Title<input [name]="draft.id + '-title'" [(ngModel)]="draftEdits[draft.id].title" maxlength="500" required /></label>
                      <label>Description<textarea [name]="draft.id + '-description'" [(ngModel)]="draftEdits[draft.id].description" maxlength="20000" rows="3"></textarea></label>
                      <div class="draft-form-grid">
                        <label>Category<input [name]="draft.id + '-category'" [(ngModel)]="draftEdits[draft.id].category" maxlength="240" /></label>
                        <label>Image reference<input [name]="draft.id + '-image'" [(ngModel)]="draftEdits[draft.id].imageRef" maxlength="500" placeholder="seller-upload://..." /></label>
                        <label>Intended price<input [name]="draft.id + '-price'" [(ngModel)]="draftEdits[draft.id].intendedPrice" inputmode="decimal" /></label>
                        <label>Currency<input [name]="draft.id + '-currency'" [(ngModel)]="draftEdits[draft.id].currency" maxlength="3" /></label>
                      </div>
                      <label>Compliance JSON<textarea [name]="draft.id + '-compliance'" [(ngModel)]="draftEdits[draft.id].complianceJson" rows="3" spellcheck="false"></textarea></label>
                      <button class="button" type="submit" [disabled]="draftSaving() === draft.id">{{ draftSaving() === draft.id ? 'Saving…' : 'Save draft' }}</button>
                    </form>
                    <p class="muted">{{ draft.missing_fields.length ? 'Missing: ' + draft.missing_fields.join(', ') : 'All required fields present' }}</p>
                    <div class="actions">
                      @if (draft.human_review_state !== 'approved' && !draft.missing_fields.length) {
                        <button class="button primary" type="button" (click)="approve(draft)">Approve as HUMAN</button>
                      }
                      @if (draft.human_review_state === 'approved') { <span class="success">Approved for future submission</span> }
                    </div>
                  } @else {
                    <p class="muted">No draft exists yet.</p>
                    <button class="button" type="button" (click)="createDraft(channel)">Start {{ channelLabel(channel) }} draft</button>
                  }
                </article>
              }
            </div>
          </section>

          <section class="card" aria-labelledby="variants-title">
            <div class="section-heading"><div><p class="eyebrow">Product master</p><h2 id="variants-title">Variants</h2></div></div>
            <p class="muted">Use one stable key per sellable combination. SKU uniqueness is enforced per owner and stale edits are rejected.</p>
            <form class="variant-form" (ngSubmit)="addVariant()">
              <label>Variant key<input name="new-variant-key" [(ngModel)]="newVariantKey" required maxlength="120" placeholder="default or blue-small" /></label>
              <label>Title<input name="new-variant-title" [(ngModel)]="newVariantTitle" maxlength="160" /></label>
              <label>SKU<input name="new-variant-sku" [(ngModel)]="newVariantSku" maxlength="100" /></label>
              <label>Options JSON<input name="new-variant-options" [(ngModel)]="newVariantOptions" placeholder='{"size":"M","color":"Blue"}' /></label>
              <button class="button primary" type="submit" [disabled]="variantSaving()">{{ variantSaving() ? 'Saving…' : 'Add variant' }}</button>
            </form>
            @if (!detail()!.variants.length) { <p class="muted">No variants have been added. Product SKU and core attributes remain the source of truth.</p> }
            @for (variant of detail()!.variants; track variant.id) {
              <form class="variant-row" (ngSubmit)="saveVariant(variant)">
                <label class="sr-only" [for]="variant.id + '-title'">Variant title</label><input [id]="variant.id + '-title'" [name]="variant.id + '-title'" [(ngModel)]="variantEdits[variant.id].title" maxlength="160" />
                <span>{{ variant.variant_key }}</span><span>{{ variant.sku || 'SKU not assigned' }}</span><span class="badge">{{ variant.status }}</span>
                <button class="button" type="submit" [disabled]="variantSaving() === variant.id">{{ variantSaving() === variant.id ? 'Saving…' : 'Save title' }}</button>
                @if (variant.status !== 'archived') { <button class="button danger" type="button" (click)="archiveVariant(variant)">Archive</button> }
              </form>
            }
          </section>
        }
      } @else {
        <app-page-header
          eyebrow="Seller Catalog"
          title="Product master & listing preparation"
          description="A clear, owner-scoped workspace for turning selected product context into channel-ready drafts. Marketplace publication is intentionally disabled."
        >
          <a page-header-actions class="button primary" routerLink="/products/new">Create product</a>
        </app-page-header>
        <section class="trust-banner" aria-label="Catalog guidance"><strong>Next step</strong><span>Select a product below, then complete its draft and approve it explicitly as HUMAN.</span></section>
        @if (listLoading()) { <app-loading-state message="Loading catalog products..." /> }
        @else if (error()) { <app-error-state title="Catalog products are unavailable" [message]="error()" retryLabel="Retry" (retry)="loadList()" /> }
        @else if (!products()?.items?.length) { <app-empty-state title="Your catalog is empty" message="Create a product or convert a HUMAN-selected Product Opportunity before preparing a listing."><a class="button" routerLink="/products/new">Create a product</a><a class="button" routerLink="/intelligence/product-opportunities">Review opportunities</a></app-empty-state> }
        @else {
          <section class="catalog-filters" aria-label="Catalog filters">
            <label>Search products<input type="search" [value]="catalogSearch()" (input)="updateSearch($event)" placeholder="Name, SKU, or category" /></label>
            <label>Status<select [value]="catalogStatus()" (change)="updateStatus($event)"><option value="all">All statuses</option><option value="draft">Draft</option><option value="active">Active</option><option value="archived">Archived</option></select></label>
            <p class="muted">{{ filteredProducts().length }} product{{ filteredProducts().length === 1 ? '' : 's' }} shown.</p>
          </section>
          @if (!filteredProducts().length) {
            <app-empty-state title="No matching products" message="Try a different search or status filter." />
          } @else {
          <section class="product-grid" aria-label="Seller catalog products">
            @for (product of filteredProducts(); track product.id) {
              <article class="card product-card">
                <div class="section-heading"><div><p class="eyebrow">{{ product.category || 'Uncategorized' }}</p><h2>{{ product.name }}</h2></div><span class="badge">{{ product.status }}</span></div>
                <p>{{ product.short_description || product.description || 'No seller description recorded yet.' }}</p>
                <dl class="facts compact"><div><dt>SKU</dt><dd>{{ product.sku || 'Not assigned' }}</dd></div><div><dt>Brand</dt><dd>{{ product.brand_name }}</dd></div></dl>
                <div class="actions"><a class="button primary" [routerLink]="['/catalog', product.id]">Open catalog workspace</a><a class="button" [routerLink]="['/products', product.id]">View product</a></div>
              </article>
            }
          </section>
          }
        }
      }
    </main>
  `,
  styleUrl: './catalog-workspace.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogWorkspaceComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly catalog = inject(CatalogService);
  private readonly productService = inject(ProductService);
  readonly selectedId = this.route.snapshot.paramMap.get('id');
  readonly channels: readonly CatalogChannel[] = ['amazon_in', 'flipkart'];
  readonly products = signal<PaginatedProductResponse | null>(null);
  readonly detail = signal<CatalogProductDetails | null>(null);
  readonly readiness = signal<CatalogReadiness | null>(null);
  readonly images = signal<CatalogProductImage[]>([]);
  readonly mediaAssets = signal<MediaAssetOption[]>([]);
  readonly economics = signal<CatalogEconomics | null>(null);
  readonly imagesLoading = signal(Boolean(this.selectedId));
  readonly economicsLoading = signal(Boolean(this.selectedId));
  readonly imageSaving = signal(false);
  readonly variantSaving = signal<string | null>(null);
  readonly selectedMediaId = signal('');
  readonly newImageAlt = signal('');
  readonly newImagePrimary = signal(false);
  newVariantKey = '';
  newVariantTitle = '';
  newVariantSku = '';
  newVariantOptions = '{}';
  readonly variantEdits: Record<string, VariantEditState> = {};
  readonly catalogSearch = signal('');
  readonly catalogStatus = signal<'all' | 'draft' | 'active' | 'archived'>('all');
  readonly draftEdits: Record<string, DraftEditState> = {};
  readonly draftSaving = signal<string | null>(null);
  readonly listLoading = signal(!this.selectedId);
  readonly detailLoading = signal(Boolean(this.selectedId));
  readonly error = signal('');

  constructor() {
    if (this.selectedId) void this.loadDetail();
    else void this.loadList();
  }

  async loadList(): Promise<void> {
    this.listLoading.set(true);
    this.error.set('');
    try {
      this.products.set(await this.productService.list({ allBrands: true, pageSize: 100 }));
    } catch (error) {
      this.error.set(ProductService.errorMessage(error));
    } finally {
      this.listLoading.set(false);
    }
  }

  async loadDetail(): Promise<void> {
    if (!this.selectedId) return;
    this.detailLoading.set(true);
    this.error.set('');
    try {
      const [detail, readiness] = await Promise.all([
        this.catalog.getProduct(this.selectedId),
        this.catalog.readiness(this.selectedId),
      ]);
      this.detail.set(detail);
      this.images.set(detail.images || []);
      for (const variant of detail.variants) this.variantEdits[variant.id] = { title: variant.title };
      for (const draft of detail.listing_drafts) this.draftEdits[draft.id] = this.toDraftEdit(draft);
      this.readiness.set(readiness);
      void this.loadMediaAssets();
      this.economicsLoading.set(true);
      try {
        this.economics.set(await this.catalog.economics(this.selectedId));
      } catch {
        this.economics.set({
          product_id: this.selectedId,
          available: false,
          opportunity_id: null,
          assessment_id: null,
          projection: null,
          reason: 'Canonical economics could not be loaded. Refresh to retry.',
        });
      } finally {
        this.economicsLoading.set(false);
      }
    } catch (error) {
      this.error.set(CatalogService.errorMessage(error));
    } finally {
      this.detailLoading.set(false);
    }
  }

  async loadMediaAssets(): Promise<void> {
    this.imagesLoading.set(true);
    try {
      const result = await this.catalog.media();
      this.mediaAssets.set(
        result.items.filter((item) => item.status === 'ready' && item.mime_type.startsWith('image/')),
      );
    } catch {
      this.mediaAssets.set([]);
    } finally {
      this.imagesLoading.set(false);
    }
  }

  selectMedia(event: Event): void {
    this.selectedMediaId.set((event.target as HTMLSelectElement).value);
  }

  mediaPreview(path: string): string {
    if (/^https?:\/\//i.test(path)) return path;
    return `${environment.apiUrl.replace(/\/api\/v1$/, '')}${path}`;
  }

  async attachImage(): Promise<void> {
    if (!this.selectedId || !this.selectedMediaId()) return;
    this.imageSaving.set(true);
    this.error.set('');
    try {
      await this.catalog.attachImage(this.selectedId, {
        media_id: this.selectedMediaId(),
        alt_text: this.newImageAlt() || null,
        position: this.images().length,
        is_primary: this.newImagePrimary() || !this.images().length,
      });
      this.selectedMediaId.set('');
      this.newImageAlt.set('');
      this.newImagePrimary.set(false);
      await this.loadDetail();
    } catch (error) {
      this.error.set(CatalogService.errorMessage(error));
    } finally {
      this.imageSaving.set(false);
    }
  }

  async updateImageAlt(image: CatalogProductImage, event: Event): Promise<void> {
    const altText = (event.target as HTMLInputElement).value;
    try {
      await this.catalog.updateImage(image, { alt_text: altText });
      await this.loadDetail();
    } catch (error) {
      this.error.set(CatalogService.errorMessage(error));
    }
  }

  async setPrimary(image: CatalogProductImage): Promise<void> {
    try {
      await this.catalog.updateImage(image, { is_primary: true });
      await this.loadDetail();
    } catch (error) {
      this.error.set(CatalogService.errorMessage(error));
    }
  }

  async removeImage(image: CatalogProductImage): Promise<void> {
    try {
      await this.catalog.removeImage(image);
      await this.loadDetail();
    } catch (error) {
      this.error.set(CatalogService.errorMessage(error));
    }
  }

  async addVariant(): Promise<void> {
    if (!this.selectedId) return;
    let options: Record<string, unknown>;
    try {
      options = JSON.parse(this.newVariantOptions || '{}') as Record<string, unknown>;
    } catch {
      this.error.set('Variant options must be valid JSON.');
      return;
    }
    this.variantSaving.set('new');
    try {
      await this.catalog.createVariant(this.selectedId, {
        variant_key: this.newVariantKey,
        title: this.newVariantTitle,
        sku: this.newVariantSku || null,
        option_values: options,
      });
      this.newVariantKey = '';
      this.newVariantTitle = '';
      this.newVariantSku = '';
      this.newVariantOptions = '{}';
      await this.loadDetail();
    } catch (error) {
      this.error.set(CatalogService.errorMessage(error));
    } finally {
      this.variantSaving.set(null);
    }
  }

  async saveVariant(variant: CatalogVariant): Promise<void> {
    const edit = this.variantEdits[variant.id];
    if (!edit) return;
    this.variantSaving.set(variant.id);
    try {
      await this.catalog.updateVariant(variant, { title: edit.title });
      await this.loadDetail();
    } catch (error) {
      this.error.set(CatalogService.errorMessage(error));
    } finally {
      this.variantSaving.set(null);
    }
  }

  async archiveVariant(variant: CatalogVariant): Promise<void> {
    this.variantSaving.set(variant.id);
    try {
      await this.catalog.updateVariant(variant, { status: 'archived' });
      await this.loadDetail();
    } catch (error) {
      this.error.set(CatalogService.errorMessage(error));
    } finally {
      this.variantSaving.set(null);
    }
  }

  draftFor(channel: CatalogChannel): CatalogListingDraft | undefined {
    return this.detail()?.listing_drafts.find((draft) => draft.channel === channel);
  }

  filteredProducts() {
    const query = this.catalogSearch().trim().toLowerCase();
    const status = this.catalogStatus();
    return (this.products()?.items ?? []).filter((product) => {
      const matchesQuery = !query || `${product.name} ${product.sku ?? ''} ${product.category ?? ''}`.toLowerCase().includes(query);
      return matchesQuery && (status === 'all' || product.status === status);
    });
  }

  updateSearch(event: Event): void {
    this.catalogSearch.set((event.target as HTMLInputElement).value);
  }

  updateStatus(event: Event): void {
    this.catalogStatus.set(
      (event.target as HTMLSelectElement).value as 'all' | 'draft' | 'active' | 'archived',
    );
  }

  private toDraftEdit(draft: CatalogListingDraft): DraftEditState {
    const imageRef = draft.image_refs[0];
    return {
      title: draft.title,
      description: draft.description,
      category: draft.category || '',
      imageRef:
        typeof imageRef === 'string'
          ? imageRef
          : imageRef === undefined
            ? ''
            : JSON.stringify(imageRef),
      intendedPrice: draft.intended_price_amount || '',
      currency: draft.intended_currency || '',
      complianceJson: JSON.stringify(draft.compliance || {}, null, 2),
    };
  }

  async saveDraft(draft: CatalogListingDraft): Promise<void> {
    const edit = this.draftEdits[draft.id];
    if (!edit) return;
    let compliance: Record<string, unknown>;
    try {
      compliance = JSON.parse(edit.complianceJson || '{}') as Record<string, unknown>;
    } catch {
      this.error.set('Compliance details must be valid JSON before saving the draft.');
      return;
    }
    this.draftSaving.set(draft.id);
    this.error.set('');
    try {
      await this.catalog.updateListingDraft(draft, {
        title: edit.title,
        description: edit.description,
        category: edit.category || null,
        image_refs: edit.imageRef ? [edit.imageRef] : [],
        intended_price_amount: edit.intendedPrice || null,
        intended_currency: edit.currency || null,
        compliance,
      });
      await this.loadDetail();
    } catch (error) {
      this.error.set(CatalogService.errorMessage(error));
    } finally {
      this.draftSaving.set(null);
    }
  }

  channelLabel(channel: CatalogChannel): string {
    return channel === 'amazon_in' ? 'Amazon India' : 'Flipkart';
  }

  async createDraft(channel: CatalogChannel): Promise<void> {
    if (!this.selectedId) return;
    try {
      await this.catalog.createListingDraft(this.selectedId, {
        channel,
        title: this.detail()?.product.name || '',
        description: this.detail()?.product.description || '',
        category: this.detail()?.product.category,
        idempotency_key: `catalog-${this.selectedId}-${channel}`,
      });
      await this.loadDetail();
    } catch (error) {
      this.error.set(CatalogService.errorMessage(error));
    }
  }

  async approve(draft: CatalogListingDraft): Promise<void> {
    try {
      await this.catalog.reviewListingDraft(draft, 'approve');
      await this.loadDetail();
    } catch (error) {
      this.error.set(CatalogService.errorMessage(error));
    }
  }
}
