import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { BrandSummary, DashboardResponse } from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import { OperationsService } from './operations.service';

@Component({
  selector: 'app-dashboard',
  imports: [FormsModule, RouterLink],
  template: `<section class="op-page">
    <header class="op-header">
      <div>
        <h1>Operational Dashboard</h1>
        <p class="op-muted">Accurate owner-scoped work requiring attention and recent activity.</p>
      </div>
      <label
        >Brand
        <select [(ngModel)]="brandId" (ngModelChange)="load()">
          <option value="">All Brands</option>
          @for (item of brandOptions(); track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select></label
      >
    </header>
    @if (loading()) {
      <p role="status">Loading operational summary…</p>
    }
    @if (error()) {
      <p class="op-error" role="alert">{{ error() }}</p>
    }
    @if (data(); as value) {
      <div class="op-grid">
        @for (metric of cards(value); track metric.label) {
          <article class="op-card">
            <h2>{{ metric.label }}</h2>
            <p class="op-stat">{{ metric.value }}</p>
          </article>
        }
      </div>
      <article class="op-card">
        <h2>Attention required</h2>
        <div class="op-grid">
          <div>
            <strong>Pending approvals</strong>
            <p class="op-stat">{{ value.metrics.pending_approvals }}</p>
            <a routerLink="/approvals">Review</a>
          </div>
          <div>
            <strong>Failed executions</strong>
            <p class="op-stat">{{ value.metrics.failed_executions }}</p>
            <a routerLink="/execution-history">Inspect</a>
          </div>
          <div>
            <strong>Retryable failures</strong>
            <p class="op-stat">{{ value.metrics.retryable_failures }}</p>
            <a routerLink="/workflows">Resolve</a>
          </div>
        </div>
      </article>
      <article class="op-card">
        <h2>Workflow status distribution</h2>
        @for (item of chart(value); track item.label) {
          <div class="op-bar">
            <span [style.width.%]="item.percent"></span
            ><span>{{ item.label }}: {{ item.value }}</span>
          </div>
        }
        @if (!chartTotal(value)) {
          <p class="op-muted">No Workflow data yet.</p>
        }
      </article>
      <article class="op-card">
        <h2>Recent activity</h2>
        @if (!value.activity.length) {
          <p class="op-muted">No recent activity.</p>
        }
        @for (item of value.activity; track item.id) {
          <p>
            <strong>{{ item.safe_summary }}</strong
            ><br /><span class="op-muted">{{ item.timestamp }} · {{ item.category }}</span>
            @if (item.related_url) {
              · <a [routerLink]="item.related_url">View</a>
            }
          </p>
        }
      </article>
      <article class="op-card">
        <h2>Quick actions</h2>
        <div class="op-actions">
          <a class="op-button" routerLink="/products/new">Create Product</a
          ><a class="op-button" routerLink="/ai/generate">Generate AI Content</a
          ><a class="op-button" routerLink="/approvals">Review Approvals</a
          ><a class="op-button" routerLink="/workflows/new">Create Workflow</a
          ><a class="op-button" routerLink="/publishing/new">Publish Content</a
          ><a class="op-button secondary" routerLink="/execution-history">Execution History</a>
        </div>
      </article>
    }
  </section>`,
  styleUrl: './operations.css',
})
export class DashboardComponent implements OnInit {
  readonly brands = inject(BrandService);
  private readonly api = inject(OperationsService);
  readonly data = signal<DashboardResponse | null>(null);
  readonly brandOptions = signal<BrandSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  brandId = '';
  ngOnInit(): void {
    void this.init();
  }
  private async init(): Promise<void> {
    await Promise.all([
      this.brands.list({ pageSize: 100 }).then((x) => this.brandOptions.set(x.items)),
      this.brands.loadActive(),
    ]);
    this.brandId = this.brands.activeBrand()?.id ?? '';
    await this.load();
  }
  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      this.data.set(await this.api.dashboard(this.brandId));
    } catch {
      this.error.set('Some operational data could not be loaded.');
    } finally {
      this.loading.set(false);
    }
  }
  cards(value: DashboardResponse) {
    const m = value.metrics;
    return [
      { label: 'Total Brands', value: m.total_brands },
      { label: 'Total Products', value: m.total_products },
      { label: 'Active Products', value: m.active_products },
      { label: 'Pending Approvals', value: m.pending_approvals },
      { label: 'Approved Artifacts', value: m.approved_artifacts },
      { label: 'Active Destinations', value: m.active_destinations },
      { label: 'Publishing Success', value: m.successful_executions },
      { label: 'Publishing Failed', value: m.failed_executions },
      { label: 'Waiting Workflows', value: m.waiting_workflows },
      { label: 'Completed Workflows', value: m.completed_workflows },
      { label: 'Failed Workflows', value: m.failed_workflows },
    ];
  }
  chartTotal(v: DashboardResponse) {
    return v.metrics.waiting_workflows + v.metrics.completed_workflows + v.metrics.failed_workflows;
  }
  chart(v: DashboardResponse) {
    const total = this.chartTotal(v) || 1;
    return [
      { label: 'Waiting', value: v.metrics.waiting_workflows },
      { label: 'Completed', value: v.metrics.completed_workflows },
      { label: 'Failed', value: v.metrics.failed_workflows },
    ].map((x) => ({ ...x, percent: (x.value / total) * 100 }));
  }
}
