import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import type {
  BrandSummary,
  MediaAsset,
  ShopifyRemoteItem,
  WordPressAuthor,
  WordPressTerm,
} from '@vayujit/shared';
import { environment } from '../../environments/environment';
import { BrandService } from '../brands/brand.service';
import { MediaService } from '../media/media.service';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-destination-form',
  imports: [ReactiveFormsModule, RouterLink],
  template: ` <section class="pub-page">
    <header>
      <h1>{{ editing() ? 'Edit' : 'Create' }} publishing destination</h1>
      <p class="pub-muted">
        Destinations contain publishing preferences only. Connector credentials are configured
        separately and are never stored here.
      </p>
    </header>
    @if (loading()) {
      <p role="status">Loading destination form…</p>
    }
    @if (error()) {
      <p class="pub-error" role="alert">{{ error() }}</p>
    }
    <form class="pub-card pub-form" [formGroup]="form" (ngSubmit)="save()">
      <label
        >Destination name <input formControlName="name" maxlength="160" />
        @if (touchedInvalid('name')) {
          <span class="pub-error">Enter a destination name.</span>
        }</label
      ><label
        >Connector
        <select formControlName="connector_key">
          <option value="mock_publisher_v1">Deterministic local mock</option>
          <option value="wordpress">WordPress</option>
          <option value="shopify">Shopify</option>
        </select></label
      ><label
        >Brand scope
        <select formControlName="brand_id">
          <option value="">All Brands</option>
          @for (brand of brands(); track brand.id) {
            <option [value]="brand.id">{{ brand.name }}</option>
          }
        </select></label
      ><label
        >Channel name <input formControlName="channel_name" maxlength="100" />
        @if (touchedInvalid('channel_name')) {
          <span class="pub-error">Enter a channel name.</span>
        }</label
      ><label
        >Publication prefix
        <input
          formControlName="publication_prefix"
          maxlength="20"
          aria-describedby="prefix-help"
        /><span id="prefix-help" class="pub-muted"
          >1–20 letters, numbers, hyphens, or underscores.</span
        >
        @if (touchedInvalid('publication_prefix')) {
          <span class="pub-error">Use only letters, numbers, hyphens, or underscores.</span>
        }
      </label>
      @if (development) {
        <details class="pub-dev">
          <summary>Development testing</summary>
          <p>
            These controls deliberately simulate connector failures and are hidden in production
            builds.
          </p>
          <label
            ><input type="checkbox" formControlName="simulate_failure" /> Simulate failure</label
          ><label
            >Failure type
            <select formControlName="failure_type">
              <option value="retryable">Retryable</option>
              <option value="non_retryable">Permanent</option>
            </select></label
          >
        </details>
      }
      @if (form.controls.connector_key.value === 'wordpress') {
        <fieldset>
          <legend>WordPress mapping</legend>
          <label
            >Post status
            <select formControlName="post_status">
              <option value="draft">Draft</option>
              <option value="publish">Publish</option>
            </select></label
          >
          <section>
            <label>Search categories <input #categorySearch /></label>
            <button type="button" (click)="loadCategories(categorySearch.value)">Search</button>
            <button type="button" (click)="loadCategories(categorySearch.value, true)">
              Refresh
            </button>
            @if (taxonomyBusy()) {
              <p role="status">Loading categories…</p>
            }
            @for (category of categories(); track category.id) {
              <label
                ><input
                  type="checkbox"
                  [checked]="selectedId('category_ids', category.id)"
                  (change)="toggleId('category_ids', category.id)"
                />
                {{ category.name }}</label
              >
            } @empty {
              <p>No categories found.</p>
            }
          </section>
          <section>
            <label>Search tags <input #tagSearch /></label>
            <button type="button" (click)="loadTags(tagSearch.value)">Search</button>
            <button type="button" (click)="loadTags(tagSearch.value, true)">Refresh</button>
            @for (tag of tags(); track tag.id) {
              <label
                ><input
                  type="checkbox"
                  [checked]="selectedId('tag_ids', tag.id)"
                  (change)="toggleId('tag_ids', tag.id)"
                />
                {{ tag.name }}</label
              >
            } @empty {
              <p>No tags found.</p>
            }
          </section>
          <label
            >Author
            <select formControlName="author_id">
              <option value="">Use WordPress default</option>
              @for (author of authors(); track author.id) {
                <option [value]="author.id">
                  {{ author.name }}{{ author.username ? ' · ' + author.username : '' }}
                </option>
              }
            </select>
          </label>
          <button type="button" (click)="loadAuthors('', true)">Refresh authors</button>
          <label
            >Featured-image policy
            <select formControlName="featured_image_policy">
              <option value="none">No featured image</option>
              <option value="optional">Optional image</option>
              <option value="required">Required image</option>
            </select>
          </label>
          <label
            >Default media
            <select formControlName="default_media_id">
              <option value="">No default media</option>
              @for (media of mediaItems(); track media.id) {
                <option [value]="media.id">
                  {{ media.safe_filename }} · {{ media.width }}×{{ media.height }}
                </option>
              }
            </select>
          </label>
          <a routerLink="/settings/publishing/connectors/wordpress"
            >Configure WordPress credentials</a
          >
        </fieldset>
      }
      @if (form.controls.connector_key.value === 'shopify') {
        <fieldset>
          <legend>Shopify product mapping</legend>
          <label
            >Default product status
            <select formControlName="shopify_status">
              <option value="draft">Draft</option>
              <option value="active">Allow explicit activation</option>
            </select>
          </label>
          <label>Default vendor <input formControlName="default_vendor" maxlength="255" /></label>
          <label
            >Default product type <input formControlName="default_product_type" maxlength="255"
          /></label>
          <label
            >Default tags
            <input formControlName="default_tags" placeholder="tag one, tag two" maxlength="2000"
          /></label>
          <section>
            <label>Search collections <input #collectionSearch /></label>
            <button type="button" (click)="loadShopifyCollections(collectionSearch.value)">
              Search
            </button>
            <button type="button" (click)="loadShopifyCollections(collectionSearch.value, true)">
              Refresh
            </button>
            @for (collection of shopifyCollections(); track collection.id) {
              <label
                ><input
                  type="checkbox"
                  [checked]="selectedRemoteId('shopify_collection_ids', collection.id)"
                  (change)="toggleRemoteId('shopify_collection_ids', collection.id)"
                />
                {{ collection.name }}</label
              >
            } @empty {
              <p>No collections loaded.</p>
            }
          </section>
          <section>
            <button type="button" (click)="loadShopifyPublications(true)">
              Refresh publications
            </button>
            @for (publication of shopifyPublications(); track publication.id) {
              <label
                ><input
                  type="checkbox"
                  [checked]="selectedRemoteId('shopify_publication_ids', publication.id)"
                  (change)="toggleRemoteId('shopify_publication_ids', publication.id)"
                />
                {{ publication.name }}</label
              >
            } @empty {
              <p>Publication discovery may be unavailable; draft creation remains supported.</p>
            }
          </section>
          <label
            >Media policy
            <select formControlName="shopify_media_policy">
              <option value="fail">Fail safely</option>
              <option value="draft_without_media">Create draft without media</option>
              <option value="degraded">Create degraded recovery item</option>
            </select>
          </label>
          <p class="pub-muted">Inventory quantities are never written by this destination.</p>
          <a routerLink="/settings/publishing/connectors/shopify">Configure Shopify credentials</a>
        </fieldset>
      }
      <div class="pub-actions">
        <button [disabled]="busy() || form.invalid">
          {{ busy() ? 'Saving…' : 'Save destination' }}</button
        ><a class="pub-button secondary" routerLink="/publishing/destinations">Cancel</a>
      </div>
    </form>
  </section>`,
  styleUrl: './publishing.css',
})
export class DestinationFormComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(PublishingService);
  private readonly brandsApi = inject(BrandService);
  private readonly mediaApi = inject(MediaService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly brands = signal<BrandSummary[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly editing = signal(false);
  readonly development = !environment.production;
  readonly categories = signal<WordPressTerm[]>([]);
  readonly tags = signal<WordPressTerm[]>([]);
  readonly authors = signal<WordPressAuthor[]>([]);
  readonly mediaItems = signal<MediaAsset[]>([]);
  readonly taxonomyBusy = signal(false);
  readonly shopifyCollections = signal<ShopifyRemoteItem[]>([]);
  readonly shopifyPublications = signal<ShopifyRemoteItem[]>([]);
  private id = '';
  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(160)]],
    connector_key: this.fb.nonNullable.control<'mock_publisher_v1' | 'wordpress' | 'shopify'>(
      'mock_publisher_v1',
      Validators.required,
    ),
    brand_id: [''],
    channel_name: ['', [Validators.required, Validators.maxLength(100)]],
    publication_prefix: ['PUB', [Validators.required, Validators.pattern(/^[A-Za-z0-9_-]{1,20}$/)]],
    simulate_failure: [false],
    failure_type: this.fb.nonNullable.control<'retryable' | 'non_retryable'>('non_retryable'),
    post_status: this.fb.nonNullable.control<'draft' | 'publish'>('draft'),
    category_ids: [''],
    tag_ids: [''],
    author_id: [''],
    featured_image_policy: this.fb.nonNullable.control<'none' | 'optional' | 'required'>('none'),
    default_media_id: [''],
    shopify_status: this.fb.nonNullable.control<'draft' | 'active'>('draft'),
    default_vendor: [''],
    default_product_type: [''],
    default_tags: [''],
    shopify_collection_ids: [''],
    shopify_publication_ids: [''],
    shopify_media_policy: this.fb.nonNullable.control<'fail' | 'draft_without_media' | 'degraded'>(
      'fail',
    ),
  });
  ngOnInit(): void {
    this.form.controls.connector_key.valueChanges.subscribe((key) => {
      const channel = this.form.controls.channel_name;
      const prefix = this.form.controls.publication_prefix;
      if (key !== 'mock_publisher_v1') {
        channel.clearValidators();
        prefix.clearValidators();
      } else {
        channel.setValidators([Validators.required, Validators.maxLength(100)]);
        prefix.setValidators([Validators.required, Validators.pattern(/^[A-Za-z0-9_-]{1,20}$/)]);
      }
      channel.updateValueAndValidity();
      prefix.updateValueAndValidity();
    });
    void this.load();
  }
  touchedInvalid(name: keyof typeof this.form.controls) {
    const control = this.form.controls[name];
    return control.touched && control.invalid;
  }
  private async load() {
    try {
      const brands = await this.brandsApi.list({ includeArchived: false, pageSize: 100 });
      this.brands.set(brands.items);
      this.mediaItems.set((await this.mediaApi.list({ pageSize: 100 })).items);
      this.id = this.route.snapshot.paramMap.get('id') ?? '';
      this.editing.set(Boolean(this.id));
      if (this.id) {
        const item = await this.api.destination(this.id);
        const configuration = item.configuration;
        this.form.patchValue({
          name: item.name,
          connector_key:
            item.connector_key === 'wordpress' || item.connector_key === 'shopify'
              ? item.connector_key
              : 'mock_publisher_v1',
          brand_id: item.brand_id ?? '',
          ...('channel_name' in configuration
            ? {
                channel_name: configuration.channel_name,
                publication_prefix: configuration.publication_prefix,
                simulate_failure: configuration.simulate_failure,
                failure_type: configuration.failure_type,
              }
            : 'post_status' in configuration
              ? {
                  post_status: configuration.post_status,
                  category_ids: configuration.category_ids.join(', '),
                  tag_ids: configuration.tag_ids.join(', '),
                  author_id: configuration.author_id ? String(configuration.author_id) : '',
                  featured_image_policy: configuration.featured_image_policy,
                  default_media_id: configuration.default_media_id ?? '',
                }
              : {
                  shopify_status: configuration.default_product_status,
                  default_vendor: configuration.default_vendor,
                  default_product_type: configuration.default_product_type,
                  default_tags: configuration.default_tags.join(', '),
                  shopify_collection_ids: configuration.default_collection_ids.join(','),
                  shopify_publication_ids: configuration.default_publication_ids.join(','),
                  shopify_media_policy: configuration.media_policy,
                }),
        });
      }
      if (this.form.controls.connector_key.value === 'wordpress') {
        await Promise.all([this.loadCategories(), this.loadTags(), this.loadAuthors()]);
      } else if (this.form.controls.connector_key.value === 'shopify') {
        await Promise.all([this.loadShopifyCollections(), this.loadShopifyPublications()]);
      }
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  async save() {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    const value = this.form.getRawValue();
    const ids = (input: string) =>
      input
        .split(',')
        .map((part) => Number(part.trim()))
        .filter((part) => Number.isInteger(part) && part > 0);
    const data = {
      name: value.name,
      brand_id: value.brand_id || null,
      connector_key: value.connector_key,
      configuration:
        value.connector_key === 'wordpress'
          ? {
              post_status: value.post_status,
              category_ids: ids(value.category_ids),
              tag_ids: ids(value.tag_ids),
              author_id: value.author_id ? Number(value.author_id) : null,
              media_policy: 'fail' as const,
              featured_image_policy: value.featured_image_policy,
              default_media_id: value.default_media_id || null,
              update_existing_remote_post: true,
              content_mapping_version: 1 as const,
            }
          : value.connector_key === 'shopify'
            ? {
                default_product_status: value.shopify_status,
                default_collection_ids: this.remoteIds(value.shopify_collection_ids),
                default_publication_ids: this.remoteIds(value.shopify_publication_ids),
                default_vendor: value.default_vendor,
                default_product_type: value.default_product_type,
                default_tags: value.default_tags
                  .split(',')
                  .map((item) => item.trim())
                  .filter(Boolean),
                variant_policy: 'default_variant' as const,
                inventory_policy: 'no_inventory_write' as const,
                media_policy: value.shopify_media_policy,
                update_existing_remote_product: true,
                content_mapping_version: 1 as const,
              }
            : {
                channel_name: value.channel_name,
                publication_prefix: value.publication_prefix,
                simulate_failure: this.development ? value.simulate_failure : false,
                failure_type: this.development ? value.failure_type : ('non_retryable' as const),
              },
    };
    try {
      const item = this.editing()
        ? await this.api.updateDestination(this.id, data)
        : await this.api.createDestination(data);
      await this.router.navigate(['/publishing/destinations', item.id]);
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  selectedId(control: 'category_ids' | 'tag_ids', id: number): boolean {
    return this.form.controls[control].value.split(',').map(Number).includes(id);
  }
  toggleId(control: 'category_ids' | 'tag_ids', id: number): void {
    const values = new Set(
      this.form.controls[control].value.split(',').map(Number).filter(Boolean),
    );
    if (values.has(id)) values.delete(id);
    else values.add(id);
    this.form.controls[control].setValue([...values].join(','));
  }
  async loadCategories(search = '', refresh = false) {
    this.taxonomyBusy.set(true);
    try {
      this.categories.set(
        (await this.api.wordpressCategories(search, refresh)).items as WordPressTerm[],
      );
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.taxonomyBusy.set(false);
    }
  }
  async loadTags(search = '', refresh = false) {
    try {
      this.tags.set((await this.api.wordpressTags(search, refresh)).items as WordPressTerm[]);
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    }
  }
  async loadAuthors(search = '', refresh = false) {
    try {
      this.authors.set(
        (await this.api.wordpressAuthors(search, refresh)).items as WordPressAuthor[],
      );
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    }
  }
  private remoteIds(value: string) {
    return value.split('|').filter(Boolean);
  }
  selectedRemoteId(control: 'shopify_collection_ids' | 'shopify_publication_ids', id: string) {
    return this.remoteIds(this.form.controls[control].value).includes(id);
  }
  toggleRemoteId(control: 'shopify_collection_ids' | 'shopify_publication_ids', id: string) {
    const values = new Set(this.remoteIds(this.form.controls[control].value));
    if (values.has(id)) values.delete(id);
    else values.add(id);
    this.form.controls[control].setValue([...values].join('|'));
  }
  async loadShopifyCollections(search = '', refresh = false) {
    try {
      this.shopifyCollections.set(
        (await this.api.shopifyDiscovery('collections', search, refresh)).items,
      );
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    }
  }
  async loadShopifyPublications(refresh = false) {
    try {
      this.shopifyPublications.set(
        (await this.api.shopifyDiscovery('publications', '', refresh)).items,
      );
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    }
  }
}
