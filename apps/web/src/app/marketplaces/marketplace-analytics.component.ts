import { Component, inject, signal } from '@angular/core';
import { MarketplaceAnalytics, MarketplaceService } from './marketplace.service';

@Component({
  selector: 'app-marketplace-analytics',
  imports: [],
  template: `<section class="marketplace-page">
    <header>
      <h1>Marketplace analytics</h1>
      <p>A factual commerce summary from imported orders and settlements.</p>
    </header>
    @if (error()) {
      <p class="marketplace-error">{{ error() }}</p>
    }
    @if (summary(); as value) {
      <div class="marketplace-stats">
        <article>
          <span>Gross sales</span><strong>{{ value.gross_sales }}</strong>
        </article>
        <article>
          <span>Fees</span><strong>{{ value.fees }}</strong>
        </article>
        <article>
          <span>Orders</span><strong>{{ value.order_count }}</strong>
        </article>
        <article>
          <span>Active listings</span><strong>{{ value.active_listing_count }}</strong>
        </article>
        <article>
          <span>Estimated profit</span
          ><strong>{{
            value.profit_status === 'unavailable' ? 'Profit unavailable' : value.estimated_profit
          }}</strong>
        </article>
      </div>
      <div class="marketplace-table">
        <table>
          <caption>
            Sales by marketplace
          </caption>
          <thead>
            <tr>
              <th>Marketplace</th>
              <th>Gross sales</th>
            </tr>
          </thead>
          <tbody>
            @for (entry of salesByMarketplace(value); track entry[0]) {
              <tr>
                <td>{{ entry[0] }}</td>
                <td>{{ entry[1] }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    } @else if (!loading()) {
      <p class="marketplace-empty">Analytics are not available yet.</p>
    }
  </section>`,
  styleUrl: './marketplaces.css',
})
export class MarketplaceAnalyticsComponent {
  private readonly service = inject(MarketplaceService);
  readonly summary = signal<MarketplaceAnalytics | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  constructor() {
    void this.load();
  }
  salesByMarketplace(value: MarketplaceAnalytics): Array<[string, string]> {
    return Object.entries(value.sales_by_marketplace);
  }
  async load(): Promise<void> {
    try {
      this.summary.set(await this.service.analytics());
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
}
