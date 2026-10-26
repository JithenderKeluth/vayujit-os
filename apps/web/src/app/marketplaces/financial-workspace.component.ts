import { Component, inject, signal } from '@angular/core';
import { KeyValuePipe } from '@angular/common';

import { PageHeaderComponent } from '../shared/page-header.component';
import { EmptyStateComponent, ErrorStateComponent, LoadingStateComponent } from '../shared/state-components';
import {
  FinancialAlert,
  FinancialBusinessAgent,
  FinancialFees,
  FinancialMarketplaceComparison,
  FinancialProfitability,
  FinancialRefundImpact,
  FinancialSettlement,
  FinancialSummary,
  FinancialTrendPoint,
  MarketplaceService,
} from './marketplace.service';

@Component({
  selector: 'app-financial-workspace',
  standalone: true,
  imports: [PageHeaderComponent, EmptyStateComponent, ErrorStateComponent, LoadingStateComponent, KeyValuePipe],
  template: `
    <section class="marketplace-page financial-workspace">
      <app-page-header
        eyebrow="Sell / financials"
        title="Sales & profitability"
        description="Understand sales, marketplace deductions, direct costs, contribution, and settlement evidence from canonical order data."
      />
      <div class="marketplace-callout" role="note">
        <strong>Local evidence boundary:</strong> this workspace is read-only for marketplaces. Synthetic fixture events are clearly labelled; UNKNOWN values are not treated as zero, and no payout or marketplace write is performed.
      </div>
      <div class="marketplace-form" role="group" aria-label="Financial filters">
        <label>Marketplace
          <select [value]="marketplace()" (change)="setMarketplace($any($event.target).value)">
            <option value="">All marketplaces</option>
            <option value="amazon">Amazon</option>
            <option value="flipkart">Flipkart</option>
          </select>
        </label>
        <label>Date from
          <input type="date" [value]="dateFrom()" (change)="dateFrom.set($any($event.target).value); load()" />
        </label>
        <label>Date to
          <input type="date" [value]="dateTo()" (change)="dateTo.set($any($event.target).value); load()" />
        </label>
        <button type="button" (click)="load()">Refresh evidence</button>
      </div>
      @if (error()) {
        <app-error-state title="Financial evidence is unavailable" [message]="error()" retryLabel="Retry" (retry)="load()" />
      }
      @if (loading()) {
        <app-loading-state message="Loading financial evidence..." />
      }
      @if (summary(); as value) {
        <div class="financial-status" [class.incomplete]="value.evidence_status !== 'observed'" role="status">
          <strong>{{ value.evidence_status === 'unknown' ? 'No financial evidence yet' : 'Evidence status: ' + value.evidence_status }}</strong>
          <span>Basis: {{ value.basis }} · Calculation {{ value.calculation_version }}</span>
        </div>
        <div class="marketplace-stats" role="region" aria-label="Sales summary">
          <article><span>Gross sales</span><strong>{{ value.currency }} {{ value.gross_sales }}</strong><small>GMV / sale events</small></article>
          <article><span>Net sales</span><strong>{{ value.currency }} {{ value.net_sales }}</strong><small>After discounts and refunds</small></article>
          <article><span>Fees & deductions</span><strong>{{ value.fees === 'UNKNOWN' ? 'UNKNOWN' : value.currency + ' ' + value.fees }}</strong><small>Observed or modelled evidence</small></article>
          <article><span>Known direct costs</span><strong>{{ value.known_direct_costs === 'UNKNOWN' ? 'UNKNOWN' : value.currency + ' ' + value.known_direct_costs }}</strong><small>COGS evidence only</small></article>
          <article><span>Contribution</span><strong>{{ value.contribution === 'UNKNOWN' ? 'UNKNOWN' : value.currency + ' ' + value.contribution }}</strong><small>{{ value.estimated_profit ? 'Fully qualified estimate' : 'Partial; missing inputs' }}</small></article>
          <article><span>Orders / events</span><strong>{{ value.order_count }} / {{ value.event_count }}</strong><small>{{ provenanceLabel(value) }}</small></article>
        </div>
        <p role="note" aria-label="Financial evidence provenance">{{ provenanceLabel(value) }}. These figures are not independently verified real financial information. Source classification does not change the recorded amounts.</p>
        @if (value.missing_inputs.length) {
          <div class="marketplace-error" role="alert">
            <strong>Review before using profitability:</strong>
            <ul>@for (item of value.missing_inputs; track item) { <li>{{ item.replace('_', ' ') }}</li> }</ul>
            <span>Profit and margin remain UNKNOWN until the required evidence is recorded.</span>
          </div>
        }
        @if (alerts()?.alerts?.length) {
          <section class="marketplace-error" role="region" aria-labelledby="financial-alerts-heading">
            <h2 id="financial-alerts-heading">Financial alerts</h2>
            <ul>@for (alert of alerts()!.alerts; track alert.code) { <li><strong>{{ alert.severity }}:</strong> {{ alert.message }}</li> }</ul>
          </section>
        }
        @if (trends()?.rows?.length) {
          <section class="marketplace-card" aria-labelledby="revenue-trend-heading">
            <h2 id="revenue-trend-heading">Revenue trend</h2>
            <div class="marketplace-table" tabindex="0" role="region" aria-label="Revenue trend table"><table>
              <caption>Server-calculated daily sales trend</caption>
              <thead><tr><th scope="col">Date</th><th scope="col">Gross sales</th><th scope="col">Net sales</th><th scope="col">Refunds</th><th scope="col">Fees</th><th scope="col">Evidence</th></tr></thead>
              <tbody>@for (point of trends()!.rows; track point.date) { <tr><th scope="row">{{ point.date }}</th><td>{{ point.gross_sales }}</td><td>{{ point.net_sales }}</td><td>{{ point.refunds }}</td><td>{{ point.fees }}</td><td>{{ point.evidence_status }}</td></tr> }</tbody>
            </table></div>
          </section>
        }
        @if (comparison()?.rows?.length) {
          <section class="marketplace-card" aria-labelledby="marketplace-comparison-heading">
            <h2 id="marketplace-comparison-heading">Marketplace comparison</h2>
            <div class="marketplace-table" tabindex="0" role="region" aria-label="Marketplace comparison table"><table>
              <caption>Owner-scoped channel comparison</caption>
              <thead><tr><th scope="col">Marketplace</th><th scope="col">Gross sales</th><th scope="col">Net sales</th><th scope="col">Fees</th><th scope="col">Contribution</th><th scope="col">Evidence</th></tr></thead>
              <tbody>@for (row of comparison()!.rows; track row.marketplace) { <tr><th scope="row">{{ row.marketplace }}</th><td>{{ row.gross_sales }}</td><td>{{ row.net_sales }}</td><td>{{ row.fees }}</td><td>{{ row.contribution }}</td><td>{{ row.evidence_status }}</td></tr> }</tbody>
            </table></div>
          </section>
        }
        @if (refundImpact(); as refund) {
          <section class="marketplace-callout" aria-labelledby="refund-impact-heading">
            <h2 id="refund-impact-heading">Refund impact</h2>
            <p><strong>{{ refund.total_refunds === 'UNKNOWN' ? 'UNKNOWN' : refund.currency + ' ' + refund.total_refunds }}</strong> explicit refund evidence · {{ refund.evidence_status }}</p>
            <small>{{ refund.basis }}</small>
          </section>
        }
        @if (fees(); as feeData) {
          <section class="marketplace-card" aria-labelledby="fee-breakdown-heading">
            <h2 id="fee-breakdown-heading">Fee breakdown</h2>
            @if (feeData.fees | keyvalue; as feeEntries) {
              @if (feeEntries.length) {
                <dl class="financial-breakdown">@for (entry of feeEntries; track entry.key) { <div><dt>{{ entry.key }}</dt><dd>{{ feeData.currency }} {{ entry.value }}</dd></div> }</dl>
              } @else { <app-empty-state title="No fee evidence yet" message="Record observed or explicitly modelled deductions before using fee comparisons." /> }
            }
          </section>
        }
        <section class="marketplace-card">
          <h2>Product profitability</h2>
          @if (profitability()?.rows?.length) {
            <div class="marketplace-table" tabindex="0" role="region" aria-label="Product profitability table"><table>
              <caption>Server-calculated product contribution</caption>
              <thead><tr><th scope="col">Product</th><th scope="col">Gross sales</th><th scope="col">Deductions</th><th scope="col">Known costs</th><th scope="col">Contribution</th><th scope="col">Evidence</th></tr></thead>
              <tbody>@for (row of profitability()!.rows; track row['product_id']) { <tr><th scope="row">{{ row['product_id'] || 'Unmapped SKU' }}</th><td>{{ row['gross_sales'] }}</td><td>{{ row['deductions'] }}</td><td>{{ row['known_direct_costs'] }}</td><td>{{ row['estimated_profit'] || 'UNKNOWN' }}</td><td>{{ row['evidence_status'] }}</td></tr> }</tbody>
            </table></div>
          } @else { <app-empty-state title="No product profitability yet" message="Import or record an observed sale event, then add cost evidence to qualify contribution." /> }
        </section>
        <section class="marketplace-card">
          <h2>Settlement reconciliation</h2>
          @if (settlements()?.rows?.length) {
            <div class="marketplace-table" tabindex="0" role="region" aria-label="Settlement reconciliation table"><table>
              <caption>Expected versus reported settlement evidence</caption>
              <thead><tr><th scope="col">Settlement</th><th scope="col">Marketplace</th><th scope="col">Expected</th><th scope="col">Reported</th><th scope="col">Difference</th><th scope="col">State</th></tr></thead>
              <tbody>@for (row of settlements()!.rows; track row.id) { <tr><th scope="row">{{ row.settlement_key }}</th><td>{{ row.marketplace }}</td><td>{{ row.expected_amount || 'UNKNOWN' }}</td><td>{{ row.reported_amount || 'UNKNOWN' }}</td><td>{{ row.difference_amount || 'UNKNOWN' }}</td><td>{{ row.status }} ({{ row.evidence_status }})</td></tr> }</tbody>
            </table></div>
          } @else { <app-empty-state title="No settlement evidence yet" message="A reported settlement is required before a payout can be called reconciled." /> }
        </section>
        @if (businessAgent(); as agent) {
          <section class="marketplace-callout" aria-labelledby="financial-agent-heading">
            <h2 id="financial-agent-heading">Business Agent guidance</h2>
            <p>{{ agent.authority }} projection · external writes {{ agent.external_writes ? 'enabled' : 'off' }}</p>
            <ul>@for (action of agent.actions; track action.type) { <li><strong>{{ action.label }}:</strong> {{ action.reason }}</li> }</ul>
          </section>
        }
      } @else if (!loading()) {
        <app-empty-state title="Financial workspace is ready" message="Import synthetic or observed financial events through the canonical marketplace workflow to begin." />
      }
    </section>
  `,
  styleUrl: './marketplaces.css',
})
export class FinancialWorkspaceComponent {
  provenanceLabel(value: FinancialSummary): string {
    if (value.synthetic_provider) return value.provenance_status === 'MIXED' ? 'Synthetic fixture mixed with other evidence' : 'Synthetic fixture';
    return value.provenance_status === 'REPORTED' ? 'Reported evidence' : 'Provenance UNKNOWN';
  }
  private readonly service = inject(MarketplaceService);
  readonly summary = signal<FinancialSummary | null>(null);
  readonly profitability = signal<FinancialProfitability | null>(null);
  readonly settlements = signal<{ rows: FinancialSettlement[]; count: number; synthetic_provider: boolean } | null>(null);
  readonly fees = signal<FinancialFees | null>(null);
  readonly alerts = signal<{ alerts: FinancialAlert[]; evidence_status: string } | null>(null);
  readonly trends = signal<{ rows: FinancialTrendPoint[]; currency: string; basis: string } | null>(null);
  readonly comparison = signal<{ rows: FinancialMarketplaceComparison[]; currency: string; count: number } | null>(null);
  readonly refundImpact = signal<FinancialRefundImpact | null>(null);
  readonly businessAgent = signal<FinancialBusinessAgent | null>(null);
  readonly marketplace = signal('');
  readonly dateFrom = signal('');
  readonly dateTo = signal('');
  readonly loading = signal(true);
  readonly error = signal('');

  constructor() { void this.load(); }

  setMarketplace(value: string): void { this.marketplace.set(value); void this.load(); }

  async load(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const filter = this.marketplace() || undefined;
      const dateFrom = this.dateFrom() ? `${this.dateFrom()}T00:00:00Z` : undefined;
      const dateTo = this.dateTo() ? `${this.dateTo()}T23:59:59Z` : undefined;
      const [summary, profitability, fees, settlements, alerts, trends, comparison, refundImpact, businessAgent] = await Promise.all([
        this.service.financialSummary(filter, dateFrom, dateTo),
        this.service.financialProfitability(filter, dateFrom, dateTo),
        this.service.financialFees(filter, dateFrom, dateTo),
        this.service.financialSettlements(filter, dateFrom, dateTo),
        this.service.financialAlerts(filter, dateFrom, dateTo),
        this.service.financialRevenueTrends(filter, dateFrom, dateTo),
        this.service.financialMarketplaceComparison(dateFrom, dateTo),
        this.service.financialRefundImpact(filter, dateFrom, dateTo),
        this.service.financialBusinessAgent(),
      ]);
      this.summary.set(summary);
      this.profitability.set(profitability);
      this.fees.set(fees);
      this.settlements.set(settlements);
      this.alerts.set(alerts);
      this.trends.set(trends);
      this.comparison.set(comparison);
      this.refundImpact.set(refundImpact);
      this.businessAgent.set(businessAgent);
    } catch {
      this.error.set(MarketplaceService.errorMessage());
    } finally { this.loading.set(false); }
  }
}
