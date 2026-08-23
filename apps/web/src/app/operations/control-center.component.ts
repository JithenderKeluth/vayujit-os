import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { OperationsService } from './operations.service';

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
  imports: [RouterLink],
  template: `
    <section class="op-page control-center" aria-labelledby="operations-title">
      <header class="control-header">
        <div>
          <p class="eyebrow">Platform administration and release operations</p>
          <h1 id="operations-title">Operations Control Center</h1>
          <p>
            Server-authoritative health, durable work, Recovery, provider safety, and release
            readiness.
          </p>
        </div>
        @if (overview(); as value) {
          <div class="environment-banner" [attr.data-status]="value.status">
            <strong>{{ value.environment }}</strong>
            <span
              >Shopify {{ value.provider_modes['shopify'] }} · Default
              {{ value.provider_modes['default'] }}</span
            >
          </div>
        }
      </header>

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
        <p class="op-muted" role="status">Loading operational overview…</p>
      }
      @if (error()) {
        <p class="op-error" role="alert">{{ error() }}</p>
      }
      @if (overview(); as value) {
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
}
