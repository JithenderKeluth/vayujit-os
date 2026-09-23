import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { OperationsService } from './operations.service';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { PageHeaderComponent } from '../shared/page-header.component';
import { StatusBadgeComponent } from '../shared/status-badge.component';

type OperationsOverview = {
  status: string;
  environment: string;
  provider_modes: Record<string, string>;
  app_version: string;
  health: {
    status: string;
    components: Array<{ component: string; status: string; message: string }>;
  };
  workers: { enabled: boolean; items: Array<Record<string, unknown>> };
  scheduler: Record<string, unknown>;
  jobs: Record<string, number>;
  recovery: { recoverable: number };
  providers: Array<Record<string, unknown>>;
  backup: Record<string, unknown>;
  storage: Record<string, unknown>;
  security: Record<string, unknown>;
  configuration: Record<string, unknown>;
  release: Record<string, unknown>;
  alerts: Array<Record<string, unknown>>;
};

@Component({
  selector: 'app-operations-control-center',
  imports: [
    RouterLink,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
    PageHeaderComponent,
    StatusBadgeComponent,
  ],
  template: `
    <section class="op-page control-center" aria-labelledby="operations-title">
      <app-page-header
        class="control-header"
        eyebrow="Platform administration and release operations"
        title="Operations Control Center"
        headingId="operations-title"
        description="Server-authoritative health, durable work, Recovery, provider safety, and release readiness."
      >
        @if (overview(); as value) {
          <div page-header-actions class="environment-banner" [attr.data-status]="value.status">
            <strong>{{ value.environment }}</strong>
            <span
              >Shopify {{ value.provider_modes['shopify'] }} · Default
              {{ value.provider_modes['default'] }}</span
            >
            <app-status-badge [status]="value.status" [label]="value.status" tone="info" />
          </div>
        }
      </app-page-header>

      <nav class="control-nav" aria-label="Operations sections">
        <a routerLink="/operations">Overview</a>
        <a routerLink="/operations/health">Health</a>
        <a routerLink="/operations/jobs">Jobs</a>
        <a routerLink="/operations/recovery">Recovery</a>
        <a routerLink="/operations/providers">Providers</a>
        <a routerLink="/operations/backups">Backups</a>
        <a routerLink="/operations/storage">Storage</a>
        <a routerLink="/operations/security">Security</a>
        <a routerLink="/operations/audit">Audit</a>
        <a routerLink="/operations/releases">Release readiness</a>
      </nav>

      @if (loading()) {
        <app-loading-state message="Loading operational overview…" />
      }
      @if (error()) {
        <app-error-state [message]="error()" retryLabel="Try again" (retry)="load()" />
      }
      @if (overview(); as value) {
        <section class="operations-priority" aria-labelledby="attention-title">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Business operations</p>
              <h2 id="attention-title">Needs Your Attention</h2>
              <p>Authoritative issues and recovery work that may affect your workflows.</p>
            </div>
            <a class="op-button" routerLink="/operations/recovery">Open Recovery Center</a>
          </div>
          @if (value.alerts.length || value.recovery.recoverable) {
            <div class="attention-grid">
              @for (alert of value.alerts; track alert['code']) {
                <article class="attention-item">
                  <span class="alert-chip">{{ alert['severity'] }}</span>
                  <h3>{{ attentionTitle(alert['code']) }}</h3>
                  <p>{{ alert['message'] }}</p>
                  <a class="op-button" [routerLink]="attentionRoute(alert['code'])">Review issue</a>
                </article>
              }
              @if (value.recovery.recoverable) {
                <article class="attention-item">
                  <span class="alert-chip">action available</span>
                  <h3>Recoverable execution failures</h3>
                  <p>{{ value.recovery.recoverable }} item(s) have registered recovery data.</p>
                  <a class="op-button" routerLink="/operations/recovery">Review recovery</a>
                </article>
              }
            </div>
          } @else {
            <app-empty-state
              title="Nothing needs your attention"
              message="VAYUJIT has no current operational issues requiring action."
            />
          }
        </section>

        <div class="two-column">
          <section class="op-card" aria-labelledby="active-work-title">
            <p class="eyebrow">Active work</p>
            <h2 id="active-work-title">Durable work by runtime state</h2>
            @if (jobEntries(value.jobs).length) {
              @for (entry of jobEntries(value.jobs); track entry[0]) {
                <div class="health-row">
                  <span>{{ entry[0] }}</span>
                  <strong>{{ entry[1] }}</strong>
                </div>
              }
            } @else {
              <app-empty-state
                title="No active work"
                message="No durable job states are currently reported."
              />
            }
            <a routerLink="/operations/jobs">Open advanced Job Explorer</a>
          </section>
          <section class="op-card" aria-labelledby="scheduled-work-title">
            <p class="eyebrow">Scheduled work</p>
            <h2 id="scheduled-work-title">Next operational window</h2>
            <div class="health-row">
              <span>Schedules</span><strong>{{ value.scheduler['scheduled_jobs'] || 0 }}</strong>
            </div>
            <div class="health-row">
              <span>Due jobs</span><strong>{{ value.scheduler['due_jobs'] || 0 }}</strong>
            </div>
            <div class="health-row">
              <span>Overdue schedules</span
              ><strong>{{ value.scheduler['overdue_schedules'] || 0 }}</strong>
            </div>
            <p class="op-muted">
              Scheduler and Calendar projections remain authoritative for timing and conflicts.
            </p>
            <a routerLink="/calendar">Open Calendar</a> &middot;
            <a routerLink="/publishing/schedules">Open schedules</a>
          </section>
        </div>

        <section class="op-card" aria-labelledby="recent-outcomes-title">
          <p class="eyebrow">Recent outcomes</p>
          <h2 id="recent-outcomes-title">Execution history</h2>
          <p>
            Completed, failed, cancelled, and recovered outcomes are available in the safe history
            projection.
          </p>
          <a routerLink="/execution-history">Open execution history</a>
        </section>

        <div class="alert-strip">
          @for (alert of value.alerts; track alert['code']) {
            <span class="alert-chip">{{ alert['severity'] }} · {{ alert['message'] }}</span>
          }
          @if (!value.alerts.length) {
            <span class="alert-chip good">No active operational alerts</span>
          }
        </div>

        <div class="op-grid metric-grid">
          <article class="op-card">
            <h2>Overall</h2>
            <strong>{{ value.status }}</strong>
            <p>{{ value.app_version }}</p>
          </article>
          <article class="op-card">
            <h2>Workers</h2>
            <strong>{{ value.workers.items.length }}</strong>
            <p>{{ value.workers.enabled ? 'Enabled' : 'Disabled' }}</p>
          </article>
          <article class="op-card">
            <h2>Recoverable</h2>
            <strong>{{ value.recovery.recoverable }}</strong>
            <p>Jobs requiring review</p>
          </article>
          <article class="op-card">
            <h2>Backups</h2>
            <strong>{{ value.backup['status'] }}</strong>
            <p>{{ value.backup['latest'] || 'No backup recorded' }}</p>
          </article>
          <article class="op-card">
            <h2>Storage</h2>
            <strong>{{ value.storage['total_bytes'] }}</strong>
            <p>owned media bytes</p>
          </article>
          <article class="op-card">
            <h2>Security</h2>
            <strong>{{ value.security['emergency_stop'] ? 'STOPPED' : 'RUNNING' }}</strong>
            <p>Mutation boundary</p>
          </article>
        </div>

        <div class="two-column">
          <article class="op-card">
            <h2>System health</h2>
            <p>
              <strong>{{ value.health.status }}</strong>
            </p>
            @for (component of value.health.components; track component.component) {
              <div class="health-row">
                <span>{{ component.component }}</span
                ><strong>{{ component.status }}</strong>
              </div>
            }
          </article>
          <article class="op-card">
            <h2>Durable jobs</h2>
            @for (entry of jobEntries(value.jobs); track entry[0]) {
              <div class="health-row">
                <span>{{ entry[0] }}</span
                ><strong>{{ entry[1] }}</strong>
              </div>
            }
            <a routerLink="/operations/jobs">Open Job Explorer</a>
          </article>
        </div>

        <article class="op-card">
          <h2>Provider registry</h2>
          <div class="provider-grid">
            @for (provider of value.providers; track provider['key']) {
              <div class="provider-row">
                <strong>{{ provider['provider'] }}</strong
                ><span>{{ provider['status'] }}</span
                ><small>{{ provider['mode'] }}</small>
              </div>
            }
          </div>
        </article>
      }
    </section>
  `,
  styleUrl: './operations.css',
})
export class ControlCenterComponent implements OnInit {
  private readonly api = inject(OperationsService);
  readonly overview = signal<OperationsOverview | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');

  ngOnInit(): void {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      this.overview.set((await this.api.controlOverview()) as OperationsOverview);
      this.error.set('');
    } catch {
      this.error.set('Operations data is unavailable. Check the authenticated API connection.');
    } finally {
      this.loading.set(false);
    }
  }

  jobEntries(value: Record<string, number>): Array<[string, number]> {
    return Object.entries(value);
  }

  attentionTitle(code: unknown): string {
    switch (code) {
      case 'failed_jobs':
        return 'Publishing jobs need review';
      case 'encryption_key_missing':
        return 'Credential configuration is incomplete';
      case 'maintenance_mode':
        return 'Maintenance mode is active';
      case 'live_mutations_enabled':
        return 'Live mutation controls are enabled';
      default:
        return 'Operational issue';
    }
  }

  attentionRoute(code: unknown): string {
    switch (code) {
      case 'failed_jobs':
        return '/operations/recovery';
      case 'encryption_key_missing':
        return '/operations/health';
      case 'maintenance_mode':
      case 'live_mutations_enabled':
        return '/operations/providers';
      default:
        return '/operations/health';
    }
  }
}
