import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { BrandSummary, DashboardResponse } from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import { OperationsService } from './operations.service';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { PageHeaderComponent } from '../shared/page-header.component';
import { StatusBadgeComponent } from '../shared/status-badge.component';

@Component({
  selector: 'app-dashboard',
  imports: [
    FormsModule,
    RouterLink,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    PageHeaderComponent,
    StatusBadgeComponent,
  ],
  template: `<section class="op-page dashboard-page" aria-labelledby="dashboard-title">
    <app-page-header
      class="op-header"
      eyebrow="Your operating workspace"
      title="What would you like to accomplish?"
      headingId="dashboard-title"
      description="Research, validate, source, launch, monitor, and optimize from one owner-scoped workspace."
    >
      <label class="dashboard-filter" page-header-actions
        >View by brand<select [(ngModel)]="brandId" (ngModelChange)="load()">
          <option value="">All Brands</option>
          @for (item of brandOptions(); track item.id) {
            <option [value]="item.id">{{ item.name }}</option>
          }
        </select></label
      >
    </app-page-header>
    <section class="dashboard-start" aria-labelledby="start-title">
      <div class="goal-panel">
        <p class="eyebrow">Start with a goal</p>
        <h2 id="start-title">Ask VAYUJIT</h2>
        <p>
          Describe a business goal in the existing Business Agent workspace. Plans, approvals,
          budgets, and execution remain governed there.
        </p>
        <a class="op-button primary" routerLink="/intelligence/business-agent"
          >Open Business Agent</a
        >
      </div>
      <div class="quick-starts" aria-labelledby="quick-start-title">
        <p class="eyebrow">Quick starts</p>
        <h2 id="quick-start-title">Choose a useful next step</h2>
        <div class="quick-start-grid">
          <a class="quick-start" routerLink="/intelligence/product-opportunities"
            ><span aria-hidden="true">⌕</span><strong>Find a product</strong
            ><small>Discover opportunities worth investigating.</small></a
          >
          <a class="quick-start" routerLink="/intelligence/product-opportunities"
            ><span aria-hidden="true">✓</span><strong>Research a product</strong
            ><small>Validate an existing opportunity with evidence.</small></a
          >
          <a class="quick-start" routerLink="/intelligence/sourcing"
            ><span aria-hidden="true">⇄</span><strong>Find suppliers</strong
            ><small>Review sourcing options and landed-cost work.</small></a
          >
          <a class="quick-start" routerLink="/campaigns"
            ><span aria-hidden="true">→</span><strong>Prepare a launch</strong
            ><small>Continue into campaign and content workflows.</small></a
          >
          <a class="quick-start" routerLink="/operations"
            ><span aria-hidden="true">◷</span><strong>Monitor my business</strong
            ><small>Review operational work and issues.</small></a
          >
        </div>
      </div>
    </section>
    @if (loading()) {
      <app-loading-state message="Loading your workspace…" />
    }
    @if (error()) {
      <app-error-state [message]="error()" retryLabel="Try again" (retry)="load()" />
    }
    @if (data(); as value) {
      @if (isFirstUse(value)) {
        <app-empty-state
          title="Start your first VAYUJIT research journey"
          message="Tell VAYUJIT what you are trying to accomplish and begin an evidence-backed workflow."
          ><a class="op-button primary" routerLink="/intelligence/business-agent"
            >Start with Business Agent</a
          ></app-empty-state
        >
      }
      <section class="attention-section" aria-labelledby="attention-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Actionable work</p>
            <h2 id="attention-title">Needs your attention</h2>
          </div>
        </div>
        @if (attentionItems(value); as items) {
          @if (items.length) {
            <div class="attention-grid">
              @for (item of items; track item.label) {
                <article class="attention-item">
                  <div>
                    <strong>{{ item.label }}</strong>
                    <p>{{ item.context }}</p>
                  </div>
                  <app-status-badge
                    [status]="item.status"
                    [label]="item.status"
                    [tone]="item.tone"
                  /><a class="op-button" [routerLink]="item.route">{{ item.action }}</a>
                </article>
              }
            </div>
          } @else {
            <p class="op-muted">Nothing requires attention right now.</p>
          }
        }
      </section>
      <section class="at-a-glance" aria-labelledby="glance-title">
        <div class="section-heading">
          <div>
            <p class="eyebrow">At a glance</p>
            <h2 id="glance-title">Your workspace</h2>
          </div>
        </div>

        <div class="op-grid dashboard-metrics">
          @for (metric of cards(value); track metric.label) {
            <article class="op-card">
              <h2>{{ metric.label }}</h2>
              <p class="op-stat">{{ metric.value }}</p>
              @if (metric.route) {
                <a class="metric-link" [routerLink]="metric.route">Open workspace</a>
              }
            </article>
          }
        </div>
      </section>
      <article class="op-card">
        <p class="eyebrow">Execution health</p>
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
        <p class="eyebrow">Audit trail</p>
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
  isFirstUse(value: DashboardResponse): boolean {
    const m = value.metrics;
    return Object.values(m).every((count) => count === 0) && value.activity.length === 0;
  }
  attentionItems(value: DashboardResponse): Array<{
    label: string;
    context: string;
    status: string;
    tone: 'info' | 'warning' | 'danger';
    action: string;
    route: string;
  }> {
    const m = value.metrics;
    return [
      ...(m.pending_approvals
        ? [
            {
              label: 'Approvals awaiting review',
              context: `${m.pending_approvals} generated artifact(s) need a decision.`,
              status: 'PENDING_REVIEW',
              tone: 'warning' as const,
              action: 'Review approvals',
              route: '/approvals',
            },
          ]
        : []),
      ...(m.failed_workflows
        ? [
            {
              label: 'Failed workflows',
              context: `${m.failed_workflows} workflow(s) are marked failed.`,
              status: 'FAILED',
              tone: 'danger' as const,
              action: 'Inspect workflows',
              route: '/workflows',
            },
          ]
        : []),
      ...(m.failed_executions
        ? [
            {
              label: 'Failed publishing executions',
              context: `${m.failed_executions} publishing execution(s) are marked failed.`,
              status: 'FAILED',
              tone: 'danger' as const,
              action: 'Inspect history',
              route: '/execution-history',
            },
          ]
        : []),
      ...(m.waiting_workflows
        ? [
            {
              label: 'Workflows waiting for approval',
              context: `${m.waiting_workflows} workflow(s) are waiting for an approval decision.`,
              status: 'WAITING_FOR_APPROVAL',
              tone: 'info' as const,
              action: 'Review workflows',
              route: '/workflows',
            },
          ]
        : []),
      ...(m.retryable_failures
        ? [
            {
              label: 'Retryable publishing failures',
              context: `${m.retryable_failures} failed execution(s) are marked retryable.`,
              status: 'RETRYABLE',
              tone: 'warning' as const,
              action: 'Inspect history',
              route: '/execution-history',
            },
          ]
        : []),
    ];
  }
  cards(value: DashboardResponse): Array<{ label: string; value: number; route: string }> {
    const m = value.metrics;
    return [
      { label: 'Total brands', value: m.total_brands, route: '/brands' },
      { label: 'Products', value: m.total_products, route: '/products' },
      { label: 'Active products', value: m.active_products, route: '/products' },
      { label: 'Approvals waiting', value: m.pending_approvals, route: '/approvals' },
      { label: 'Approved artifacts', value: m.approved_artifacts, route: '/ai/history' },
      {
        label: 'Active destinations',
        value: m.active_destinations,
        route: '/publishing/destinations',
      },
      { label: 'Publishing success', value: m.successful_executions, route: '/execution-history' },
      { label: 'Publishing failed', value: m.failed_executions, route: '/execution-history' },
      { label: 'Waiting workflows', value: m.waiting_workflows, route: '/workflows' },
      { label: 'Completed workflows', value: m.completed_workflows, route: '/workflows' },
      { label: 'Failed workflows', value: m.failed_workflows, route: '/workflows' },
      { label: 'Retryable failures', value: m.retryable_failures, route: '/execution-history' },
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
