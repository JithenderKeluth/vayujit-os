import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import {
  MarketplaceInventory,
  MarketplaceListing,
  MarketplaceOrder,
  MarketplaceService,
  MarketplaceSettlement,
  ProductChannelIntelligence,
} from './marketplace.service';

interface ChannelRow {
  marketplace: string;
  listing: MarketplaceListing | null;
  inventory: MarketplaceInventory | null;
  orders: MarketplaceOrder[];
  settlements: MarketplaceSettlement[];
  intelligence: ProductChannelIntelligence | null;
}

@Component({
  selector: 'app-product-channel-view',
  imports: [RouterLink],
  template: `
    <section class="marketplace-page">
      <header>
        <h1>Product channel view</h1>
        <p>
          Canonical Product <code>{{ productId }}</code> projected independently into each
          marketplace channel.
        </p>
      </header>
      @if (error()) {
        <p class="marketplace-error" role="alert">{{ error() }}</p>
      }
      <div class="marketplace-table">
        <table>
          <caption>
            Product marketplace projections
          </caption>
          <thead>
            <tr>
              <th>Marketplace</th>
              <th>Listing</th>
              <th>SKU</th>
              <th>Price</th>
              <th>Inventory</th>
              <th>Orders/sales</th>
              <th>Fees</th>
              <th>Contribution</th>
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
                <td>{{ row.marketplace }}</td>
                <td>{{ row.listing?.status || 'Not listed' }}</td>
                <td>{{ row.listing?.marketplace_sku || '—' }}</td>
                <td>
                  {{ row.settlements[0]?.gross_amount || '—' }}
                  {{ row.settlements[0]?.currency || '' }}
                </td>
                <td>{{ row.inventory?.available_quantity ?? '—' }}</td>
                <td>{{ row.orders.length }}</td>
                <td>{{ fees(row) }}</td>
                <td>{{ contribution(row) }}</td>
                <td>{{ row.listing?.drift_state || 'none' }}</td>
                <td>{{ row.listing?.content_artifact_version ?? '—' }}</td>
                <td>{{ row.intelligence?.readiness || 'Not generated' }}</td>
                <td>{{ row.intelligence?.search_score ?? '—' }}</td>
                <td><a [routerLink]="channelPath(row.marketplace, row.listing?.id)">Open</a></td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>
  `,
  styleUrl: './marketplaces.css',
})
export class ProductChannelViewComponent {
  private readonly service = inject(MarketplaceService);
  private readonly route = inject(ActivatedRoute);
  readonly productId = this.route.snapshot.paramMap.get('id') || '';
  readonly channels = signal<ChannelRow[]>([]);
  readonly error = signal('');
  private readonly registry: Record<string, string> = {
    amazon: '/marketplaces/amazon',
    flipkart: '/marketplaces/flipkart',
    meesho: '/marketplaces/meesho',
  };
  constructor() {
    void this.load();
  }
  channelPath(marketplace: string, listingId?: string): string {
    return listingId
      ? `/marketplaces/listings/${listingId}/${marketplace}`
      : this.registry[marketplace] || '/marketplaces';
  }
  fees(row: ChannelRow): string {
    return String(row.settlements.reduce((sum, item) => sum + Number(item.fee_amount || 0), 0));
  }
  contribution(row: ChannelRow): string {
    return String(
      row.settlements.reduce(
        (sum, item) =>
          sum +
          Number(item.gross_amount || 0) -
          Number(item.refund_amount || 0) -
          Number(item.fee_amount || 0),
        0,
      ),
    );
  }
  async load(): Promise<void> {
    try {
      const [listings, inventory, orders, settlements, intelligence] = await Promise.all([
        this.service.listings(),
        this.service.inventory(),
        this.service.orders(),
        this.service.settlements(),
        this.service.productChannelIntelligence(this.productId),
      ]);
      const channels = new Set<string>([
        ...[...listings, ...inventory, ...orders, ...settlements]
          .map((item) => item.marketplace)
          .filter((marketplace): marketplace is string => Boolean(marketplace)),
        ...intelligence.map((item) => item.channel),
      ]);
      this.channels.set(
        [...channels].sort().map((marketplace) => ({
          marketplace,
          listing:
            listings.find(
              (item) => item.product_id === this.productId && item.marketplace === marketplace,
            ) || null,
          inventory:
            inventory.find(
              (item) => item.product_id === this.productId && item.marketplace === marketplace,
            ) || null,
          orders: orders.filter((item) => item.marketplace === marketplace),
          settlements: settlements.filter((item) => item.marketplace === marketplace),
          intelligence: intelligence.find((item) => item.channel === marketplace) || null,
        })),
      );
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    }
  }
}
