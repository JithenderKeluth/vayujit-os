import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe, JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { EmptyStateComponent, ErrorStateComponent, LoadingStateComponent } from '../shared/state-components';
import { PageHeaderComponent } from '../shared/page-header.component';
import { StatusBadgeComponent } from '../shared/status-badge.component';
import { ActionCenterService, OperationalBriefing, OperationalHistoryEntry, OperationalPolicy, OperationalSignal } from './action-center.service';

@Component({
  selector: 'app-action-center',
  standalone: true,
  imports: [FormsModule, RouterLink, DatePipe, JsonPipe, PageHeaderComponent, StatusBadgeComponent, EmptyStateComponent, ErrorStateComponent, LoadingStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="action-center-page" aria-labelledby="action-center-title">
      <app-page-header eyebrow="Business Agent / operations" title="Action Center" headingId="action-center-title" description="Evidence-based operational issues that need your attention. Review the source before changing any canonical record.">
        <a page-header-actions class="op-button" routerLink="/intelligence/business-agent">Back to Business Agent</a>
      </app-page-header>
      <section class="action-boundary" role="note"><strong>Controlled workspace:</strong> recommendations are advisory. External marketplace, supplier, procurement, payment, and inventory-publication actions are blocked here and require their canonical HUMAN workflow.</section>
      @if (error()) { <app-error-state title="Action Center is unavailable" [message]="error()" retryLabel="Retry" (retry)="load()" /> }
      @if (loading()) { <app-loading-state message="Scanning canonical seller data..." /> }
      @if (briefing(); as brief) {
        <section class="briefing-card" aria-labelledby="briefing-title">
          <div class="section-heading"><div><p class="eyebrow">Today</p><h2 id="briefing-title">Operational briefing</h2></div><button type="button" class="op-button" (click)="refreshScan()">Refresh scan</button></div>
          <p>{{ brief.counts.active }} active issue(s): {{ brief.counts.critical }} critical and {{ brief.counts.high }} high priority.</p>
          <p class="muted">{{ brief.changes_since_previous }} Last generated {{ brief.generated_at | date: 'short' }}. Read-only: {{ brief.read_only }}.</p>
          @if (brief.priorities.length) { <ul class="priority-list">@for (item of brief.priorities; track item.id) { <li><strong>{{ item.title }}</strong><span>{{ item.recommended_action }}</span></li> }</ul> }
        </section>
      }
      @if (notice()) { <p class="action-success" role="status">{{ notice() }}</p> }
      <section class="filters" role="group" aria-label="Action Center filters">
        <label>Search <input [(ngModel)]="search" (ngModelChange)="filtersChanged()" type="search" placeholder="Search issues" /></label>
        <label>Category <select [(ngModel)]="category" (ngModelChange)="filtersChanged()"><option value="">All categories</option><option value="catalog">Catalog</option><option value="inventory">Inventory</option><option value="orders">Orders</option><option value="financial">Financial</option><option value="supplier">Supplier</option></select></label>
        <label>Severity <select [(ngModel)]="severity" (ngModelChange)="filtersChanged()"><option value="">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
        <label>Status <select [(ngModel)]="status" (ngModelChange)="filtersChanged()"><option value="">Active</option><option value="NEW">New</option><option value="ACKNOWLEDGED">Acknowledged</option><option value="SNOOZED">Snoozed</option><option value="REOPENED">Reopened</option><option value="RESOLVED">Resolved</option><option value="STALE">Stale evidence</option></select></label>
      </section>
      @if (visibleSignals().length) {
        <section class="signal-list" aria-labelledby="signals-title">
          <div class="section-heading"><div><p class="eyebrow">Prioritized work</p><h2 id="signals-title">{{ total() }} matching issue(s)</h2></div><span class="muted">Sorted by deterministic priority</span></div>
          @for (item of visibleSignals(); track item.id) {
            <article class="signal-card" [class.critical]="item.severity === 'critical'" [class.high]="item.severity === 'high'">
              <div class="signal-header"><div><span class="signal-category">{{ item.category }} / {{ item.signal_type }}</span><h3>{{ item.title }}</h3></div><app-status-badge [status]="item.severity" [label]="item.severity" [tone]="item.severity === 'critical' ? 'danger' : item.severity === 'high' ? 'warning' : 'info'" /></div>
              <p>{{ item.explanation }}</p>
              <dl class="signal-meta"><div><dt>Status</dt><dd>{{ item.status }}</dd></div><div><dt>Confidence</dt><dd>{{ item.confidence }}</dd></div><div><dt>Evidence</dt><dd>{{ item.evidence_quality }}</dd></div><div><dt>Priority</dt><dd>{{ item.priority_score }}</dd></div><div><dt>Source</dt><dd>{{ item.source_authority }}</dd></div></dl>
              @if (item.uncertainty) { <p class="uncertainty"><strong>Uncertainty:</strong> {{ item.uncertainty }}</p> }
              <p class="recommended"><strong>Recommended next step:</strong> {{ item.recommended_action }}</p>
              <div class="signal-actions">
                <button type="button" class="op-button" (click)="inspect(item)">Inspect evidence</button>
                @if (item.status === 'STALE') { <p>Historical evidence only. Refresh the scan to review current signals.</p> }
                @else if (item.status === 'RESOLVED') { <button type="button" class="op-button" (click)="reopen(item)">Reopen</button> }
                @else {
                  <button type="button" class="op-button" (click)="acknowledge(item)" [disabled]="item.status === 'ACKNOWLEDGED'">Acknowledge</button>
                  <button type="button" class="op-button" (click)="snooze(item)">Snooze 1 hour</button>
                  <button type="button" class="op-button" (click)="resolve(item)">Resolve</button>
                }
                @if (item.source_route) { <a class="op-button" [routerLink]="item.source_route">Open source</a> }
              </div>
              @if (selected()?.id === item.id) { <div class="evidence-panel" role="region" aria-label="Selected signal evidence"><h4>Evidence and audit context</h4><p><strong>Canonical source:</strong> {{ item.source_resource_type }} / {{ item.source_resource_id || 'UNKNOWN' }}</p><pre>{{ item.evidence | json }}</pre>@if (history().length) { <h4>Resolution history</h4><ul>@for (entry of history(); track $index) { <li>{{ entry.from_status || 'created' }} → {{ entry.to_status }} · {{ entry.actor_type }} · {{ entry.created_at }}</li> }</ul> }</div> }
            </article>
          }
        </section>
      } @else if (!loading() && !error()) { <app-empty-state title="No matching issues" message="No signals match the selected status and filters. Change the filters or refresh the scan after seller data changes." /> }
      @if (!loading() && !error() && total()) {
        <nav aria-label="Signal result pages"><p role="status">Showing {{ offset + 1 }}–{{ offset + data().length }} of {{ total() }} matching issues</p><button type="button" class="op-button" [disabled]="offset === 0" (click)="changePage(-1)">Previous page</button><button type="button" class="op-button" [disabled]="offset + pageSize >= total()" (click)="changePage(1)">Next page</button></nav>
      }
      @if (policy(); as value) {
        <section class="policy-card" aria-labelledby="policy-title"><div class="section-heading"><div><p class="eyebrow">Safety controls</p><h2 id="policy-title">Automation policy</h2></div><span class="muted">{{ value.policy_version }}</span></div><p>Local read-only scans are allowed. Sensitive actions remain disabled by default and require a canonical HUMAN authority.</p><label class="check-row"><input type="checkbox" [checked]="value.dry_run" (change)="setDryRun($any($event.target).checked)" /> Dry-run mode</label><label class="check-row"><input type="checkbox" [checked]="value.emergency_stop" (change)="setEmergencyStop($any($event.target).checked)" /> Emergency stop</label><p class="muted">External writes: disabled. AI/SYSTEM actors cannot impersonate HUMAN approval.</p></section>
      }
    </section>
  `,
  styleUrl: './action-center.css',
})
export class ActionCenterComponent implements OnInit {
  private readonly api = inject(ActionCenterService);
  readonly data = signal<OperationalSignal[]>([]);
  readonly briefing = signal<OperationalBriefing | null>(null);
  readonly policy = signal<OperationalPolicy | null>(null);
  readonly selected = signal<OperationalSignal | null>(null);
  readonly history = signal<OperationalHistoryEntry[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly notice = signal('');
  readonly total = signal(0);
  readonly pageSize = 25;
  offset = 0;
  private requestVersion = 0;
  search = '';
  category = '';
  severity = '';
  status = '';

  ngOnInit(): void { void this.load(); }

  async load(): Promise<void> {
    const version = ++this.requestVersion;
    this.loading.set(true); this.error.set('');
    this.data.set([]); this.selected.set(null); this.history.set([]);
    try {
      const response = await this.api.load({ status: this.status || undefined, category: this.category, severity: this.severity, search: this.search.trim(), limit: this.pageSize, offset: this.offset });
      if (version !== this.requestVersion) return;
      if (response.total > 0 && this.offset >= response.total) {
        this.offset = Math.floor((response.total - 1) / this.pageSize) * this.pageSize;
        await this.load(); return;
      }
      if (response.total === 0) this.offset = 0;
      this.data.set(response.signals); this.briefing.set(response.briefing); this.policy.set(response.policy);
      this.total.set(response.total);
    } catch { if (version === this.requestVersion) { this.total.set(0); this.error.set('Operational signals could not be loaded. Check the API and try again.'); } }
    finally { if (version === this.requestVersion) this.loading.set(false); }
  }

  filtersChanged(): void { this.offset = 0; this.notice.set(''); void this.load(); }
  changePage(direction: number): void { this.offset = Math.max(0, this.offset + direction * this.pageSize); void this.load(); }

  visibleSignals(): OperationalSignal[] {
    return this.data();
  }

  async refreshScan(): Promise<void> { this.notice.set(''); await this.api.scan(); await this.load(); this.notice.set('Canonical seller data rescanned. Signals were updated idempotently.'); }
  async inspect(item: OperationalSignal): Promise<void> { const detail = await this.api.detail(item.id); this.selected.set(item); this.history.set(detail.history); }
  async acknowledge(item: OperationalSignal): Promise<void> { await this.api.transition(item.id, 'acknowledge'); await this.load(); this.notice.set('Signal acknowledged.'); }
  async snooze(item: OperationalSignal): Promise<void> { await this.api.snooze(item.id, new Date(Date.now() + 60 * 60 * 1000).toISOString()); await this.load(); this.notice.set('Signal snoozed for one hour.'); }
  async resolve(item: OperationalSignal): Promise<void> { await this.api.transition(item.id, 'resolve'); await this.load(); this.notice.set('Signal resolved locally; the source record was not changed.'); }
  async reopen(item: OperationalSignal): Promise<void> { await this.api.transition(item.id, 'reopen'); await this.load(); this.notice.set('Signal reopened locally; no external action was taken.'); }
  async setDryRun(value: boolean): Promise<void> { this.policy.set(await this.api.updatePolicy({ dry_run: value })); }
  async setEmergencyStop(value: boolean): Promise<void> { this.policy.set(await this.api.updatePolicy({ emergency_stop: value })); }
}
