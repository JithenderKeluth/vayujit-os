import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { BrandSummary, DashboardResponse } from '@vayujit/shared';
import { BrandService } from '../brands/brand.service';
import { DailyStatus, OperationsService } from './operations.service';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { PageHeaderComponent } from '../shared/page-header.component';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import { CommerceJourneyContextComponent } from '../commerce-journey-context.component';
import { CommerceJourneyService } from '../commerce-journey.service';
import type { CommerceJourney } from '../commerce-journey.types';

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
    CommerceJourneyContextComponent,
  ],
  template: `<section class="op-page dashboard-page" aria-labelledby="dashboard-title">
    <app-page-header
      class="op-header"
      eyebrow="Your operating workspace"
      title="What should you do today?"
      headingId="dashboard-title"
      description="Start with a goal, continue your journey, or take the next useful action."
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
    <app-commerce-journey-context [showEmptyState]="false" />
    @if (loading()) {
      <app-loading-state message="Loading your workspace..." />
    }
    @if (error()) {
      <app-error-state
        title="Workspace data is unavailable"
        [message]="error()"
        retryLabel="Try again"
        (retry)="load()"
      />
    }
    @if (data(); as value) {
      <section class="goal-panel" aria-labelledby="daily-status-title">
        <h2 id="daily-status-title">Daily seller status</h2>
        <p>
          Installation-wide canonical records, independent of the brand filter. Destinations and
          recorded accounts are not proof of live marketplace authorization.
        </p>
        @if (daily(); as status) {
          <p role="status">
            Read at {{ status.loadedAt }}. This is retrieval time, not verification of source
            freshness.
          </p>
          @if (status.unavailable.length) {
            <p role="alert">
              Unavailable: {{ status.unavailable.join(', ') }}. A failed read is UNKNOWN, not zero
              or healthy.
            </p>
          }
          <ul>
            <li>
              <a routerLink="/operations/action-center">Review operational evidence</a>:
              {{
                status.briefing ? status.briefing.counts.active + ' active issue(s)' : 'UNKNOWN'
              }}. Scan evidence must be reviewed; no action was executed.
            </li>
            <li>
              <a routerLink="/marketplaces/inventory">Review stock ledger</a>:
              {{
                status.inventory === null
                  ? 'UNKNOWN'
                  : status.inventory.length + ' inventory record(s)'
              }}. Product master quantity is not ledger stock.
            </li>
            <li>
              <a routerLink="/marketplaces/orders">Review orders</a>:
              {{
                status.orders === null
                  ? 'UNKNOWN'
                  : status.orders.length + ' returned record(s), up to the API limit'
              }}. Synthetic records: {{ syntheticOrders(status) }}.
            </li>
            <li>
              <a routerLink="/marketplaces/accounts">Review marketplace prerequisites</a>:
              {{
                status.accounts === null
                  ? 'UNKNOWN'
                  : status.accounts.length + ' recorded account(s)'
              }}. No verified live connection is inferred from configuration.
            </li>
            <li>
              <a routerLink="/marketplaces/financials">Review sales and contribution evidence</a>:
              {{ status.financial ? status.financial.evidence_status : 'UNKNOWN' }}. Revenue is not
              profit; missing cost or fee evidence blocks profitability.
            </li>
          </ul>
          @if (status.financial?.synthetic_provider) {
            <p class="trust-note">
              Synthetic financial evidence is present. It is not real seller revenue.
            </p>
          }
        } @else {
          <p>
            Daily operational evidence is unavailable; review the source workspaces. No healthy or
            zero state is inferred.
          </p>
        }
      </section>
      @if (isFirstUse(value)) {
        <section class="goal-panel first-use-panel" aria-labelledby="start-title">
          <p class="eyebrow">Start with a goal</p>
          <h2 id="start-title">What are you trying to achieve?</h2>
          <p>
            Tell VAYUJIT what you want to achieve and keep research, sourcing, decisions, and launch
            connected.
          </p>
          <a class="op-button primary" routerLink="/intelligence/business-agent"
            >Start with Business Agent</a
          >
        </section>
        <app-empty-state
          title="Your workspace is ready"
          message="Begin with a product idea, supplier question, or business goal."
        />
      } @else if (activeJourney(); as journey) {
        <section class="active-goal-panel" aria-labelledby="active-goal-title">
          <div>
            <p class="eyebrow">Active goal</p>
            <h2 id="active-goal-title">{{ journeyGoalSummary(journey) }}</h2>
            <p>{{ journeyStatus(journey) }}</p>
          </div>
          @if (journey.trust; as trust) {
            <p class="trust-note">{{ trust.label }}</p>
          }
        </section>
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
                    [label]="item.statusLabel"
                    [tone]="item.tone"
                  /><a class="op-button" [routerLink]="item.route">{{ item.action }}</a>
                </article>
              }
            </div>
          } @else {
            <p class="op-muted">
              No publishing or journey alerts in this summary. Review the operational briefing for
              stock, orders and finance; this does not establish business readiness.
            </p>
          }
        }
      </section>
      @if (opportunities(value); as items) {
        @if (items.length) {
          <section class="opportunities-section" aria-labelledby="opportunities-title">
            <div class="section-heading">
              <div>
                <p class="eyebrow">Useful findings</p>
                <h2 id="opportunities-title">Opportunities and findings</h2>
              </div>
            </div>
            <div class="opportunity-grid">
              @for (item of items; track item.label) {
                <article class="opportunity-item">
                  <strong>{{ item.label }}</strong>
                  <p>{{ item.context }}</p>
                  <a class="op-button" [routerLink]="item.route">{{ item.action }}</a>
                </article>
              }
            </div>
          </section>
        }
      }
      @if (!isFirstUse(value)) {
        <section class="at-a-glance" aria-labelledby="glance-title">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Business activity</p>
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
      }
      <section class="quick-starts" aria-labelledby="quick-start-title">
        <p class="eyebrow">Quick actions</p>
        <h2 id="quick-start-title">Take the next useful step</h2>
        <div class="quick-start-grid">
          <a class="quick-start" routerLink="/intelligence/product-opportunities"
            ><span aria-hidden="true">+</span><strong>Start product research</strong
            ><small>Find and compare opportunities worth investigating.</small></a
          >
          <a class="quick-start" routerLink="/operations/action-center"
            ><span aria-hidden="true">+</span><strong>Open Action Center</strong
            ><small>Review evidence-backed operational issues and next steps.</small></a
          >
          <a class="quick-start" routerLink="/intelligence/sourcing"
            ><span aria-hidden="true">+</span><strong>Find suppliers</strong
            ><small>Review sourcing options for a product.</small></a
          >
          <a class="quick-start" routerLink="/ai/studio"
            ><span aria-hidden="true">+</span><strong>Create content</strong
            ><small>Prepare content for a product or launch.</small></a
          >
          <a class="quick-start" routerLink="/calendar"
            ><span aria-hidden="true">+</span><strong>View calendar</strong
            ><small>See planned work and upcoming activity.</small></a
          >
          <a class="quick-start" routerLink="/campaigns"
            ><span aria-hidden="true">+</span><strong>Prepare a launch</strong
            ><small>Continue into campaign and launch workflows.</small></a
          >
        </div>
      </section>
      <details class="advanced-dashboard">
        <summary>Advanced system health</summary>
        <article class="op-card">
          <p class="eyebrow">Technical details</p>
          <h2>Workflow status</h2>
          @for (item of chart(value); track item.label) {
            <div class="op-bar">
              <span [style.width.%]="item.percent"></span
              ><span>{{ item.label }}: {{ item.value }}</span>
            </div>
          }
          @if (!chartTotal(value)) {
            <p class="op-muted">No workflow activity yet.</p>
          }
        </article>
        <article class="op-card">
          <p class="eyebrow">Research history</p>
          <h2>Recent activity</h2>
          @if (!value.activity.length) {
            <p class="op-muted">No recent activity.</p>
          }
          @for (item of value.activity; track item.id) {
            <p>
              <strong>{{ item.safe_summary }}</strong
              ><br /><span class="op-muted">{{ item.timestamp }} - {{ item.category }}</span>
              @if (item.related_url) {
                - <a [routerLink]="item.related_url">View details</a>
              }
            </p>
          }
        </article>
      </details>
    }
  </section>`,
  styleUrl: './operations.css',
})
export class DashboardComponent implements OnInit {
  readonly brands = inject(BrandService);
  private readonly api = inject(OperationsService);
  private readonly journeyService = inject(CommerceJourneyService, { optional: true });
  readonly data = signal<DashboardResponse | null>(null);
  readonly activeJourney = signal<CommerceJourney | null>(null);
  readonly brandOptions = signal<BrandSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly daily = signal<DailyStatus | null>(null);
  private loadVersion = 0;
  brandId = '';
  ngOnInit(): void {
    void this.init();
  }
  private async init(): Promise<void> {
    try {
      await Promise.all([
        this.brands.list({ pageSize: 100 }).then((x) => this.brandOptions.set(x.items)),
        this.brands.loadActive(),
      ]);
    } catch {
      this.brandOptions.set([]);
    }
    this.brandId = this.brands.activeBrand()?.id ?? '';
    await this.load();
  }
  async load(): Promise<void> {
    const version = ++this.loadVersion;
    this.loading.set(true);
    this.error.set('');
    this.data.set(null);
    this.daily.set(null);
    this.activeJourney.set(null);
    try {
      const [dashboard, journey, daily] = await Promise.all([
        this.api.dashboard(this.brandId),
        this.loadJourney(),
        typeof this.api.dailyStatus === 'function' ? this.api.dailyStatus() : Promise.resolve(null),
      ]);
      if (version !== this.loadVersion) return;
      this.data.set(dashboard);
      this.activeJourney.set(journey);
      this.daily.set(daily);
    } catch {
      if (version === this.loadVersion)
        this.error.set('Some operational data could not be loaded.');
    } finally {
      if (version === this.loadVersion) this.loading.set(false);
    }
  }
  syntheticOrders(value: DailyStatus): string {
    return value.orders === null
      ? 'UNKNOWN'
      : String(value.orders.filter((order) => order.fake_provider === true).length);
  }
  isFirstUse(value: DashboardResponse): boolean {
    const m = value.metrics;
    return (
      this.activeJourney() === null &&
      Object.values(m).every((count) => count === 0) &&
      value.activity.length === 0
    );
  }
  attentionItems(value: DashboardResponse): Array<{
    label: string;
    context: string;
    status: string;
    statusLabel: string;
    tone: 'info' | 'warning' | 'danger';
    action: string;
    route: string;
  }> {
    const m = value.metrics;
    const items = [
      ...(m.pending_approvals
        ? [
            {
              label: 'Approvals awaiting review',
              context: `${m.pending_approvals} generated artifact(s) need a decision.`,
              status: 'PENDING_REVIEW',
              statusLabel: 'Needs review',
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
              statusLabel: 'Failed',
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
              statusLabel: 'Failed',
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
              statusLabel: 'In progress',
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
              statusLabel: 'Ready to retry',
              tone: 'warning' as const,
              action: 'Inspect history',
              route: '/execution-history',
            },
          ]
        : []),
    ];
    const reviewStage = this.activeJourney()?.stages.find((stage) =>
      ['NEEDS_REVIEW', 'BLOCKED'].includes(stage.status),
    );
    if (reviewStage) {
      items.unshift({
        label: reviewStage.label + ' needs attention',
        context:
          reviewStage.reason ||
          'Complete the ' + reviewStage.label.toLowerCase() + ' step before moving forward.',
        status: reviewStage.status,
        statusLabel: reviewStage.status === 'BLOCKED' ? 'Blocked' : 'Needs review',
        tone: reviewStage.status === 'BLOCKED' ? ('danger' as const) : ('warning' as const),
        action: 'Review ' + reviewStage.label.toLowerCase(),
        route: reviewStage.route,
      });
    }
    return items;
  }

  journeyGoalSummary(journey: CommerceJourney): string {
    const values = journey.context.values;
    const product = this.displayContext(values['product_name']);
    const category = this.displayContext(values['category']);
    const market = this.displayContext(values['marketplace']);
    if (product) return 'Research and launch ' + product;
    if (category && market) return 'Research ' + category + ' opportunities for ' + market;
    if (category) return 'Research ' + category + ' opportunities';
    if (market) return 'Research product opportunities for ' + market;
    return 'Continue your product research journey';
  }

  journeyStatus(journey: CommerceJourney): string {
    const stage =
      journey.stages.find((item) => item.status === 'IN_PROGRESS') ??
      journey.stages.find((item) => item.status === 'READY');
    return stage
      ? stage.label + ' is the next step. ' + journey.next_action.detail
      : journey.next_action.detail;
  }

  private async loadJourney(): Promise<CommerceJourney | null> {
    if (!this.journeyService) return null;
    try {
      return await this.journeyService.active();
    } catch {
      return null;
    }
  }

  private displayContext(value: unknown): string {
    return typeof value === 'string' && value.trim() ? value.trim() : '';
  }
  opportunities(value: DashboardResponse): Array<{
    label: string;
    context: string;
    action: string;
    route: string;
  }> {
    const m = value.metrics;
    return [
      ...(m.total_products > 0
        ? [
            {
              label: `${m.total_products} product${m.total_products === 1 ? '' : 's'} ready to review`,
              context: 'Keep product research and launch work moving from one workspace.',
              action: 'Review products',
              route: '/products',
            },
          ]
        : []),
      ...(m.approved_artifacts > 0
        ? [
            {
              label: `${m.approved_artifacts} content artifact${m.approved_artifacts === 1 ? '' : 's'} ready to use`,
              context: 'Approved content can move into your product and campaign workflows.',
              action: 'Open content history',
              route: '/ai/history',
            },
          ]
        : []),
      ...(m.active_destinations > 0
        ? [
            {
              label: `${m.active_destinations} configured publishing destination${m.active_destinations === 1 ? '' : 's'}`,
              context:
                'Configuration only; not a connected seller account, verified authorization or proof of sales.',
              action: 'Review destinations',
              route: '/publishing/destinations',
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
