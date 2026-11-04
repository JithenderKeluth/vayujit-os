import { HttpClient } from '@angular/common/http';
import { PageHeaderComponent } from '../shared/page-header.component';
import { EmptyStateComponent } from '../shared/state-components';
import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { CommerceJourneyNavComponent } from '../shared/commerce-journey-nav.component';
import { ErrorStateComponent } from '../shared/state-components';
import { CatalogService } from '../catalog/catalog.service';
import type { CatalogListingDraft, CatalogProductDetails } from '@vayujit/shared';
import { SellerMoneyPipe } from '../intelligence/seller-financial-format';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';
import {
  MarketplaceInventory,
  MarketplaceListing,
  MarketplaceAccount,
  MarketplaceService,
  ProductChannelIntelligence,
} from './marketplace.service';

interface ChannelRow {
  marketplace: string;
  listing: MarketplaceListing | null;
  inventory: MarketplaceInventory | null;
  accounts: MarketplaceAccount[];
  draft: CatalogListingDraft | null;
  intelligence: ProductChannelIntelligence | null;
}
interface VideoChannel {
  marketplace: string;
  current: {
    listing_id: string;
    video_version: number;
    remote_video_id: string | null;
    attachment_state: string;
    reconciliation_state: string;
  } | null;
  latest_approved_video: Record<string, unknown> | null;
  update_available: boolean;
  actions: string[];
}

export function marketplaceProjectionKey(channel: string): string | null {
  if (channel === 'amazon_in' || channel === 'amazon') return 'amazon';
  return channel === 'flipkart' || channel === 'meesho' ? channel : null;
}

@Component({
  selector: 'app-product-channel-view',
  imports: [
    BreadcrumbsComponent,
    CommerceJourneyNavComponent,
    EmptyStateComponent,
    ErrorStateComponent,

    PageHeaderComponent,
    RouterLink,
    SellerMoneyPipe,
  ],
  template: `
    <section class="marketplace-page">
      <app-breadcrumbs [items]="breadcrumbs" />
      <app-page-header
        eyebrow="Sell / product channels"
        [title]="
          product()?.product?.name
            ? product()!.product.name + ' — marketplace preparation'
            : 'Product marketplace preparation'
        "
        description="Catalog drafts, seller-account status and persisted listing evidence are separate. A configured destination is not a connected marketplace."
      />
      <app-commerce-journey-nav current="listings" />
      @if (error()) {
        <app-error-state
          title="Product Channel is unavailable"
          [message]="error()"
          retryLabel="Retry"
          (retry)="load()"
        />
      }
      @if (product()) {
        <p class="marketplace-callout">
          Local preparation only. No marketplace calls or publication occur here. Listing checks,
          HUMAN draft review, live account authorization and execution permission are separate
          gates.
        </p>
        <div class="marketplace-actions">
          <a [routerLink]="['/catalog', productId]">Return to this Catalog product</a>
          <a routerLink="/marketplaces/accounts">Review seller-account prerequisites</a>
          <a routerLink="/marketplaces/inventory/opening" [queryParams]="{ product_id: productId }"
            >Record counted opening stock</a
          >
        </div>
        <div
          class="marketplace-table"
          role="region"
          aria-label="Product marketplace preparation"
          tabindex="0"
        >
          <table>
            <caption>
              Product marketplace projections
            </caption>
            <thead>
              <tr>
                <th>Marketplace</th>
                <th>Seller account</th>
                <th>Local Catalog draft</th>
                <th>Remote listing evidence</th>
                <th>SKU</th>
                <th>Intended draft price (not sales)</th>
                <th>Inventory</th>
                <th>Drift</th>
                <th>Artifact version</th>
                <th>Content readiness</th>
                <th>SEO score</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              @for (row of channels(); track row.marketplace) {
                <tr>
                  <th scope="row">{{ row.marketplace }}</th>
                  <td>
                    @if (!row.accounts.length) {
                      Not connected — no seller account recorded
                    }
                    @for (account of row.accounts; track account.id) {
                      <p>
                        {{ account.display_name }} · {{ account.environment }} ·
                        {{ account.enabled ? 'Enabled locally' : 'Disabled' }}
                      </p>
                      <p>
                        Connection: {{ account.connection_state || 'UNKNOWN' }} · validation:
                        {{ account.validation_status }} · credentials:
                        {{ account.credential_status }} · transport:
                        {{ account.transport_mode || 'UNKNOWN' }}
                      </p>
                      <p>These recorded states are not proof of live provider certification.</p>
                    }
                  </td>
                  <td>
                    {{
                      row.draft
                        ? row.draft.status + ' · HUMAN review: ' + row.draft.human_review_state
                        : 'Not prepared'
                    }}
                    @if (row.draft?.missing_fields?.length) {
                      <p>Missing: {{ row.draft!.missing_fields.join(', ') }}</p>
                    }
                  </td>
                  <td>
                    {{
                      row.listing
                        ? row.listing.status + ' · publication: ' + row.listing.publication_state
                        : 'No persisted marketplace listing'
                    }}
                  </td>
                  <td>{{ row.listing?.marketplace_sku || '-' }}</td>
                  <td>
                    {{
                      row.draft?.intended_price_amount | sellerMoney: row.draft?.intended_currency
                    }}
                  </td>
                  <td>{{ row.inventory?.available_quantity ?? '-' }}</td>
                  <td>{{ row.listing?.drift_state || 'none' }}</td>
                  <td>{{ row.listing?.content_artifact_version ?? '-' }}</td>
                  <td>{{ row.intelligence?.readiness || 'Not generated' }}</td>
                  <td>{{ row.intelligence?.search_score ?? '-' }}</td>
                  <td>
                    <a [routerLink]="['/catalog', productId]" fragment="drafts-title"
                      >Prepare local draft</a
                    >
                    @if (row.listing) {
                      <a [routerLink]="channelPath(row.marketplace, row.listing!.id)"
                        >Review saved listing</a
                      >
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        <p>
          Product-specific sales, fees and profit are UNKNOWN here. Channel-wide orders and
          settlements are not attributed to this product or used as its price. Review canonical
          financial evidence separately.
        </p>
        @if (contentDestinations().length) {
          <section class="marketplace-card" aria-labelledby="content-destinations-title">
            <h2 id="content-destinations-title">
              Other content destinations — not seller accounts
            </h2>
            <p>
              These are content/SEO projections, not connected marketplace sales channels or proof
              of publication.
            </p>
            @for (destination of contentDestinations(); track destination.channel) {
              <p>
                {{ destination.channel }} · content readiness: {{ destination.readiness }} ·
                {{ destination.blockers.join(', ') }}
              </p>
            }
          </section>
        }
        <section class="marketplace-card" aria-labelledby="channel-video-heading">
          <h2 id="channel-video-heading">Marketplace Video</h2>
          <p>Server-projected Video readiness and actions for each channel.</p>
          <div class="marketplace-grid">
            @for (video of videoChannels(); track video.marketplace) {
              <article class="marketplace-card">
                <h3>{{ video.marketplace }}</h3>
                @if (video.current; as current) {
                  <p>
                    Listing: <code>{{ current.listing_id }}</code>
                  </p>
                  <p>
                    Current Video: v{{ current.video_version }} -
                    {{ current.remote_video_id || 'not attached' }}
                  </p>
                  <p>Remote: {{ current.attachment_state }} - {{ current.reconciliation_state }}</p>
                } @else {
                  <app-empty-state
                    title="No video attached"
                    message="Attach an approved video when this channel requires one."
                  />
                }
                @if (video.latest_approved_video) {
                  <p>
                    Latest approved Video: v{{
                      video.latest_approved_video['video_version'] || '-'
                    }}
                  </p>
                }
                <p class="marketplace-status">
                  {{
                    video.update_available
                      ? 'Update available'
                      : video.current
                        ? 'Up to date'
                        : 'No remote attachment established'
                  }}
                </p>
                <div class="marketplace-actions">
                  @for (action of video.actions; track action) {
                    <button type="button" (click)="videoAction(action)">{{ action }}</button>
                  }
                </div>
              </article>
            }
          </div>
          @if (!videoChannels().length) {
            <app-empty-state
              title="No channel video projection"
              message="A channel video projection is not available yet."
            />
          }
        </section>
      }
    </section>
  `,
  styleUrl: './marketplaces.css',
})
export class ProductChannelViewComponent {
  private readonly service = inject(MarketplaceService);
  private readonly http = inject(HttpClient);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly catalog = inject(CatalogService);
  productId = this.route.snapshot.paramMap.get('id') || '';
  private epoch = 0;
  readonly channels = signal<ChannelRow[]>([]);
  readonly contentDestinations = signal<ProductChannelIntelligence[]>([]);
  readonly videoChannels = signal<VideoChannel[]>([]);
  readonly error = signal('');
  readonly product = signal<CatalogProductDetails | null>(null);
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Products', url: '/products' },
    { label: 'Product Channels' },
  ];
  private readonly registry: Record<string, string> = {
    amazon: '/marketplaces/amazon',
    flipkart: '/marketplaces/flipkart',
    meesho: '/marketplaces/meesho',
  };
  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      this.productId = params.get('id') || '';
      void this.load();
    });
  }
  channelPath(marketplace: string, listingId?: string): string {
    return listingId
      ? `/marketplaces/listings/${listingId}/${marketplace}`
      : this.registry[marketplace] || '/marketplaces';
  }
  async load(): Promise<void> {
    const epoch = ++this.epoch,
      productId = this.productId;
    this.error.set('');
    this.product.set(null);
    this.channels.set([]);
    this.contentDestinations.set([]);
    this.videoChannels.set([]);
    try {
      const [product, accounts, listings, inventory, intelligence] = await Promise.all([
        this.catalog.getProduct(productId),
        this.service.accounts(),
        this.service.listings(),
        this.service.inventory(),
        this.service.productChannelIntelligence(productId),
      ]);
      if (epoch !== this.epoch) return;
      this.product.set(product);
      this.contentDestinations.set(
        intelligence.filter((item) => !marketplaceProjectionKey(item.channel)),
      );
      const channels = new Set<string>([
        'amazon',
        'flipkart',
        ...[...listings, ...inventory]
          .filter((item) => item.product_id === this.productId)
          .map((item) => item.marketplace)
          .filter((marketplace): marketplace is string => Boolean(marketplace)),
        ...intelligence
          .map((item) => marketplaceProjectionKey(item.channel))
          .filter((key): key is string => key !== null),
      ]);
      this.channels.set(
        [...channels].sort().map((marketplace) => ({
          marketplace,
          accounts: accounts.filter((account) => account.marketplace === marketplace),
          draft:
            product.listing_drafts.find(
              (draft) => draft.channel === (marketplace === 'amazon' ? 'amazon_in' : marketplace),
            ) || null,
          listing:
            listings.find(
              (item) => item.product_id === this.productId && item.marketplace === marketplace,
            ) || null,
          inventory:
            inventory.find(
              (item) => item.product_id === this.productId && item.marketplace === marketplace,
            ) || null,
          intelligence:
            intelligence.find((item) => marketplaceProjectionKey(item.channel) === marketplace) ||
            null,
        })),
      );
      const video = await firstValueFrom(
        this.http.get<{ channels: VideoChannel[] }>(
          `${environment.apiUrl}/marketplaces/video/product/${productId}`,
          { withCredentials: true },
        ),
      ).catch(() => null);
      if (epoch === this.epoch) this.videoChannels.set(video?.channels || []);
    } catch {
      if (epoch === this.epoch) this.error.set(MarketplaceService.errorMessage());
    }
  }
  videoAction(action: string): void {
    this.error.set(`${action} is available in the shared Marketplace Video workspace.`);
  }
}
