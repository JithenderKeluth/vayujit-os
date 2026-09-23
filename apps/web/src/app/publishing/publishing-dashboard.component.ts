import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type {
  AIHistoryItem,
  PublishingConnectorSummary,
  PublishingExecutionDetails,
} from '@vayujit/shared';
import { AIService } from '../ai/ai.service';
import { BrandService } from '../brands/brand.service';
import { BreadcrumbsComponent } from '../shared/breadcrumbs.component';
import { CommerceJourneyNavComponent } from '../shared/commerce-journey-nav.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import type { BreadcrumbItem } from '../shared/ux-foundation.types';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-publishing-dashboard',
  imports: [
    BreadcrumbsComponent,
    CommerceJourneyNavComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    RouterLink,
    StatusBadgeComponent,
  ],
  template: ` <section class="pub-page" aria-labelledby="publishing-title">
    <app-breadcrumbs [items]="breadcrumbs" />
    <header class="pub-header">
      <div>
        <h1 id="publishing-title">Mock Publishing</h1>
        <p class="pub-muted">
          Publish approved content safely to a deterministic local connector. No network request or
          real publication occurs.
        </p>
      </div>
      <div class="pub-actions">
        <a class="pub-button" routerLink="/publishing/new">Publish approved content</a
        ><a class="pub-button secondary" routerLink="/publishing/destinations/new"
          >Create destination</a
        >
      </div>
    </header>
    <app-commerce-journey-nav current="publishing" />
    @if (loading()) {
      <app-loading-state message="Loading governed publishing state..." />
    }
    @if (error()) {
      <app-error-state title="Publishing state is unavailable" [message]="error()" />
    }
    @if (!loading() && !activeBrand()) {
      <app-empty-state
        title="No active Brand"
        message="Activate a Brand before preparing a Brand-focused publication."
      >
        <a routerLink="/brands">Manage Brands</a>
      </app-empty-state>
    }
    <div class="pub-grid">
      <article class="pub-card">
        <h2>Active Brand</h2>
        <p class="pub-stat">{{ activeBrand()?.name || 'None' }}</p>
      </article>
      <article class="pub-card">
        <h2>Connector</h2>
        <p class="pub-stat">{{ connector()?.available ? 'Available' : 'Unavailable' }}</p>
        <p>{{ connector()?.name || 'Local mock' }}</p>
      </article>
      <article class="pub-card">
        <h2>Active destinations</h2>
        <p class="pub-stat">{{ activeDestinations() }}</p>
      </article>
      <article class="pub-card">
        <h2>Approved, unpublished</h2>
        <p class="pub-stat">{{ unpublished() }}</p>
      </article>
      <article class="pub-card">
        <h2>Successful</h2>
        <p class="pub-stat">{{ succeeded() }}</p>
      </article>
      <article class="pub-card">
        <h2>Failed / retryable</h2>
        <p class="pub-stat">{{ failed() }} / {{ retryable() }}</p>
      </article>
    </div>
    <article class="pub-card">
      <header class="pub-header">
        <h2>Recent executions</h2>
        <a routerLink="/publishing/executions">View all history</a>
      </header>
      @for (item of recent(); track item.id) {
        <p>
          <a [routerLink]="['/publishing/executions', item.id]"
            >{{ item.content_snapshot['product_name'] }} · {{ item.id.slice(0, 8) }}</a
          >
          <app-status-badge [status]="item.status" [label]="item.status" tone="info" />
        </p>
      } @empty {
        <app-empty-state
          title="No publishing executions yet"
          message="Approved content appears here after an existing governed publication run."
        />
      }
    </article>
  </section>`,
  styleUrl: './publishing.css',
})
export class PublishingDashboardComponent implements OnInit {
  private readonly api = inject(PublishingService);
  private readonly brands = inject(BrandService);
  private readonly ai = inject(AIService);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly connector = signal<PublishingConnectorSummary | null>(null);
  readonly recent = signal<PublishingExecutionDetails[]>([]);
  readonly activeDestinations = signal(0);
  readonly succeeded = signal(0);
  readonly failed = signal(0);
  readonly retryable = signal(0);
  readonly unpublished = signal(0);
  readonly breadcrumbs: BreadcrumbItem[] = [
    { label: 'Products', url: '/products' },
    { label: 'Publishing' },
  ];
  readonly activeBrand = this.brands.activeBrand;
  ngOnInit(): void {
    void this.load();
  }
  private async load() {
    try {
      const brand = await this.brands.loadActive();
      const [connectors, destinations, success, failed, retryable, approved] = await Promise.all([
        this.api.connectors(),
        this.api.destinations({ brandId: brand?.id, status: 'active', pageSize: 1 }),
        this.api.executions({ brandId: brand?.id, status: 'succeeded', pageSize: 5 }),
        this.api.executions({ brandId: brand?.id, status: 'failed', pageSize: 1 }),
        this.api.executions({ brandId: brand?.id, status: 'failed', retryable: true, pageSize: 1 }),
        this.ai.history({ brandId: brand?.id, artifactStatus: 'approved', pageSize: 100 }),
      ]);
      this.connector.set(connectors[0] ?? null);
      this.activeDestinations.set(destinations.total);
      this.succeeded.set(success.total);
      this.failed.set(failed.total);
      this.retryable.set(retryable.total);
      this.recent.set(success.items);
      const published = new Set(success.items.map((item) => item.artifact_id));
      this.unpublished.set(
        approved.items.filter(
          (item: AIHistoryItem) => item.artifact_id && !published.has(item.artifact_id),
        ).length,
      );
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
}
