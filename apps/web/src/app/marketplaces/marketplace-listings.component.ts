import { Component, inject, signal } from '@angular/core';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { CommerceJourneyNavComponent } from '../shared/commerce-journey-nav.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';
import { MarketplaceListing, MarketplaceService } from './marketplace.service';

@Component({
  selector: 'app-marketplace-listings',
  imports: [
    BreadcrumbsComponent,
    CommerceJourneyNavComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    StatusBadgeComponent,
  ],
  template: `<section class="marketplace-page">
    <app-breadcrumbs [items]="breadcrumbs" />
    <header>
      <h1>Marketplace listings</h1>
      <p>Review channel-specific listing state without replacing the Product source of truth.</p>
    </header>
    <app-commerce-journey-nav current="listings" />
    @if (error()) {
      <app-error-state
        title="Marketplace listings are unavailable"
        [message]="error()"
        retryLabel="Retry"
        (retry)="load()"
      />
    }
    @if (loading()) {
      <app-loading-state message="Loading saved marketplace listings..." />
    }
    @if (!items().length && !loading()) {
      <app-empty-state
        title="No marketplace listings"
        message="Create or connect a listing through the existing marketplace workflow when a channel is ready."
      />
    }
    <div class="marketplace-table">
      <table>
        <thead>
          <tr>
            <th>Marketplace</th>
            <th>Title</th>
            <th>SKU</th>
            <th>Status</th>
            <th>Drift</th>
          </tr>
        </thead>
        <tbody>
          @for (item of items(); track item.id) {
            <tr>
              <td>{{ marketplaceLabel(item.marketplace) }}</td>
              <td>{{ item.title }}</td>
              <td>{{ item.marketplace_sku || '—' }}</td>
              <td>
                <app-status-badge [status]="item.status" [label]="item.status" tone="info" />
              </td>
              <td>{{ item.drift_state }}</td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  </section>`,
  styleUrl: './marketplaces.css',
})
export class MarketplaceListingsComponent {
  private readonly service = inject(MarketplaceService);
  readonly items = signal<MarketplaceListing[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Products', url: '/products' },
    { label: 'Marketplace listings' },
  ];
  constructor() {
    void this.load();
  }
  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      this.items.set(await this.service.listings());
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally {
      this.loading.set(false);
    }
  }
  marketplaceLabel(value: string): string {
    const labels: Record<string, string> = {
      amazon: 'Amazon',
      flipkart: 'Flipkart',
      meesho: 'Meesho',
      shopify: 'Shopify',
      wordpress: 'WordPress',
    };
    return labels[value.toLowerCase()] || value;
  }
}
