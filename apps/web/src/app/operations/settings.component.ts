import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import type {
  AITemplateSummary,
  BrandSummary,
  OwnerPreferences,
  PublishingDestinationSummary,
  SessionSummary,
  SettingsResponse,
  SystemStatus,
} from '@vayujit/shared';
import { AuthService } from '../auth/auth.service';
import { AIService } from '../ai/ai.service';
import { BrandService } from '../brands/brand.service';
import { PublishingService } from '../publishing/publishing.service';
import { OperationsService } from './operations.service';

@Component({
  selector: 'app-settings',
  imports: [FormsModule, RouterLink, RouterLinkActive],
  template: `<section class="op-page">
    <header>
      <h1>Settings</h1>
      <p class="op-muted">Durable owner preferences and safe local diagnostics.</p>
    </header>
    <nav class="op-tabs" aria-label="Settings sections">
      @for (x of sections; track x[1]) {
        <a [routerLink]="['/settings', x[1]]" routerLinkActive="active">{{ x[0] }}</a>
      }
    </nav>
    @if (loading()) {
      <p role="status">Loading settings…</p>
    }
    @if (error()) {
      <p class="op-error" role="alert">{{ error() }}</p>
    }
    @if (message()) {
      <p class="op-success" role="status">{{ message() }}</p>
    }
    @if (settings(); as value) {
      @if (section() === 'general' || section() === 'profile') {
        <form class="op-card op-form" (ngSubmit)="saveProfile()">
          <h2>Owner profile</h2>
          <label>Email<input [value]="value.profile.email" disabled /></label
          ><label
            >Display name<input required maxlength="120" name="name" [(ngModel)]="displayName"
          /></label>
          <p>
            Account created: {{ value.profile.created_at }}<br />Last login:
            {{ value.profile.last_login_at || 'Not recorded' }}
          </p>
          <button [disabled]="busy()">Save profile</button>
        </form>
      }
      @if (
        section() === 'general' ||
        section() === 'appearance' ||
        section() === 'ai' ||
        section() === 'publishing'
      ) {
        <form class="op-card op-form" (ngSubmit)="savePreferences()">
          <h2>Preferences</h2>
          @if (section() === 'general') {
            <label
              >Default Brand
              <select name="defaultBrand" [(ngModel)]="preferences.default_brand_id">
                <option [ngValue]="null">No default Brand</option>
                @for (brand of brands(); track brand.id) {
                  <option [value]="brand.id">{{ brand.name }}</option>
                }
              </select>
            </label>
            @if (!brands().length) {
              <p class="op-muted">No active Brands are available.</p>
            }
          }
          @if (section() === 'ai') {
            <p>
              <a routerLink="/settings/ai/providers/openai-compatible"
                >Configure OpenAI-compatible provider</a
              >
            </p>
            <label
              >Default prompt template
              <select name="defaultTemplate" [(ngModel)]="preferences.default_prompt_template_id">
                <option [ngValue]="null">No preferred template</option>
                @for (template of templates(); track template.id) {
                  <option [value]="template.id">
                    {{ template.name }} · v{{ template.version }}
                  </option>
                }
              </select>
            </label>
            @if (!templates().length) {
              <p class="op-muted">No enabled prompt templates are available.</p>
            }
          }
          @if (section() === 'publishing') {
            <label
              >Default Publishing destination
              <select
                name="defaultDestination"
                [(ngModel)]="preferences.default_publishing_destination_id"
              >
                <option [ngValue]="null">No preferred destination</option>
                @for (destination of destinations(); track destination.id) {
                  <option [value]="destination.id">
                    {{ destination.name }} · {{ destination.connector_key }} ·
                    {{ destination.brand_name || 'All Brands' }}
                  </option>
                }
              </select>
            </label>
            @if (!destinations().length) {
              <p class="op-muted">No active Publishing destinations are available.</p>
            }
          }
          <label
            >Timezone<input
              name="timezone"
              required
              maxlength="100"
              [(ngModel)]="preferences.timezone" /></label
          ><label
            >Date format<select name="date" [(ngModel)]="preferences.date_format">
              <option value="medium">Medium</option>
              <option value="short">Short</option>
              <option value="iso">ISO</option>
            </select></label
          ><label
            >Default page size<select name="page" [(ngModel)]="preferences.default_page_size">
              @for (x of sizes; track x) {
                <option [ngValue]="x">{{ x }}</option>
              }
            </select></label
          ><label
            >Execution History page size<select
              name="historyPage"
              [(ngModel)]="preferences.execution_history_page_size"
            >
              @for (x of sizes; track x) {
                <option [ngValue]="x">{{ x }}</option>
              }
            </select></label
          ><label
            >Theme<select
              name="theme"
              [(ngModel)]="preferences.theme_preference"
              (ngModelChange)="previewTheme($event)"
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select></label
          ><label
            >Density<select name="density" [(ngModel)]="preferences.density_preference">
              <option value="comfortable">Comfortable</option>
              <option value="compact">Compact</option>
            </select></label
          ><label
            ><input
              type="checkbox"
              name="publishConfirm"
              [(ngModel)]="preferences.confirm_before_publish"
            />
            Confirm before Publishing</label
          ><label
            ><input
              type="checkbox"
              name="retryConfirm"
              [(ngModel)]="preferences.confirm_before_retry"
            />
            Confirm before retry</label
          >
          <p class="op-muted">
            AI uses the deterministic local provider by default. Publishing uses local mock
            destinations for safe testing. Configure external providers and connectors from their
            dedicated settings pages when you are ready.
          </p>
          <button [disabled]="busy()">Save preferences</button>
        </form>
      }
      @if (section() === 'security' || section() === 'profile') {
        <form class="op-card op-form" (ngSubmit)="changePassword()">
          <h2>Change password</h2>
          <label
            >Current password<input
              type="password"
              name="current"
              autocomplete="current-password"
              [(ngModel)]="current" /></label
          ><label
            >New password<input
              type="password"
              minlength="12"
              maxlength="256"
              name="password"
              autocomplete="new-password"
              [(ngModel)]="password" /></label
          ><label
            >Confirm new password<input
              type="password"
              name="confirmation"
              autocomplete="new-password"
              [(ngModel)]="confirmation" /></label
          ><button [disabled]="busy() || password.length < 12 || password !== confirmation">
            Change password
          </button>
        </form>
        <article class="op-card">
          <h2>Sessions</h2>
          @for (item of sessions(); track item.id) {
            <p>
              {{ item.current ? 'Current session' : 'Other session' }} · created
              {{ item.created_at }} · expires {{ item.expires_at }}
            </p>
          }
          <div class="op-actions">
            <button class="secondary" (click)="revoke('others')">Sign out other sessions</button
            ><button class="danger" (click)="revoke('all')">Sign out all sessions</button>
          </div>
        </article>
      }
      @if (section() === 'system') {
        <article class="op-card">
          <h2>System diagnostics</h2>
          @if (system(); as x) {
            <dl>
              <dt>Application</dt>
              <dd>{{ x.application_version }}</dd>
              <dt>Environment</dt>
              <dd>{{ x.environment }}</dd>
              <dt>API / database</dt>
              <dd>{{ x.api_status }} / {{ x.database_status }}</dd>
              <dt>Migration</dt>
              <dd>{{ x.migration_revision }} (expected {{ x.expected_revision }})</dd>
              <dt>Python</dt>
              <dd>{{ x.python_version }}</dd>
              <dt>Providers</dt>
              <dd>{{ x.providers.join(', ') }}</dd>
              <dt>Connectors</dt>
              <dd>{{ x.connectors.join(', ') }}</dd>
              <dt>Server time</dt>
              <dd>{{ x.server_time }}</dd>
            </dl>
          }
        </article>
      }
    }
  </section>`,
  styleUrl: './operations.css',
})
export class SettingsComponent implements OnInit {
  private readonly api = inject(OperationsService);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  private readonly brandApi = inject(BrandService);
  private readonly ai = inject(AIService);
  private readonly publishing = inject(PublishingService);
  readonly settings = signal<SettingsResponse | null>(null);
  readonly sessions = signal<SessionSummary[]>([]);
  readonly system = signal<SystemStatus | null>(null);
  readonly brands = signal<BrandSummary[]>([]);
  readonly templates = signal<AITemplateSummary[]>([]);
  readonly destinations = signal<PublishingDestinationSummary[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  readonly sections = [
    ['General', 'general'],
    ['Profile', 'profile'],
    ['Appearance', 'appearance'],
    ['Security', 'security'],
    ['AI', 'ai'],
    ['Publishing', 'publishing'],
    ['System', 'system'],
  ] as const;
  readonly sizes = [10, 25, 50, 100] as const;
  displayName = '';
  current = '';
  password = '';
  confirmation = '';
  preferences = {} as OwnerPreferences;
  section() {
    return this.router.url.split('/')[2] || 'general';
  }
  ngOnInit() {
    void this.load();
  }
  async load() {
    try {
      const [s, sessions, system, brands, templates, destinations] = await Promise.all([
        this.api.settings(),
        this.api.sessions(),
        this.api.system(),
        this.brandApi.list({ status: 'active', pageSize: 100 }),
        this.ai.templates(),
        this.publishing.destinations({ status: 'active', pageSize: 100 }),
      ]);
      this.settings.set(s);
      this.displayName = s.profile.full_name;
      this.preferences = { ...s.preferences };
      this.sessions.set(sessions);
      this.system.set(system);
      this.brands.set(brands.items);
      this.templates.set(templates);
      this.destinations.set(destinations.items);
      this.previewTheme(s.preferences.theme_preference);
    } catch {
      this.error.set('Unable to load settings.');
    } finally {
      this.loading.set(false);
    }
  }
  async saveProfile() {
    await this.act(async () => {
      const x = await this.api.updateProfile(this.displayName.trim());
      this.settings.set(x);
      this.message.set('Profile updated.');
    });
  }
  async savePreferences() {
    await this.act(async () => {
      const x = await this.api.updatePreferences(this.preferences);
      this.settings.set(x);
      this.preferences = { ...x.preferences };
      this.message.set('Preferences saved.');
    });
  }
  async changePassword() {
    if (this.password !== this.confirmation) return;
    await this.act(async () => {
      await this.api.changePassword(this.current, this.password, this.confirmation);
      this.current = this.password = this.confirmation = '';
      this.message.set('Password changed.');
    });
  }
  async revoke(scope: 'others' | 'all') {
    if (!confirm(`Sign out ${scope === 'all' ? 'all sessions' : 'all other sessions'}?`)) return;
    await this.act(async () => {
      await this.api.revoke(scope);
      if (scope === 'all') {
        this.auth.user.set(null);
        await this.router.navigateByUrl('/login');
      } else this.sessions.set(await this.api.sessions());
      this.message.set('Sessions revoked.');
    });
  }
  previewTheme(theme: string) {
    document.documentElement.dataset['theme'] = theme;
  }
  private async act(action: () => Promise<void>) {
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    try {
      await action();
    } catch {
      this.error.set('The setting could not be saved. Check the values and try again.');
    } finally {
      this.busy.set(false);
    }
  }
}
