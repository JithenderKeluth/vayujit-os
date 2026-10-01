import { PageHeaderComponent } from '../shared/page-header.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { Component, inject, signal } from '@angular/core';
import { MarketplaceAnalytics, MarketplaceService } from './marketplace.service';

@Component({
  selector: 'app-marketplace-analytics',
  imports: [PageHeaderComponent, EmptyStateComponent, ErrorStateComponent, LoadingStateComponent],
  template: `<section class="marketplace-page">
    <app-page-header
      eyebrow="Sell / marketplaces"
      title="Marketplace analytics"
      description="A factual commerce summary from imported orders and settlements."
    />
    @if (error()) {
      <app-error-state
        title="Marketplace analytics are unavailable"
        [message]="error()"
        retryLabel="Retry"
        (retry)="load()"
      />
    }
    @if (loading()) {
      <app-loading-state message="Loading marketplace analytics..." />
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
      <app-empty-state
        title="Analytics not available"
        message="There is not enough imported commerce data to show analytics yet."
      />
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
