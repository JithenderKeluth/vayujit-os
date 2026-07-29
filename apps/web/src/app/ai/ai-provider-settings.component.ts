import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type {
  AIModelSummary,
  AIProviderConfiguration,
  UpdateAIProviderConfiguration,
} from '@vayujit/shared';
import { AIService } from './ai.service';

@Component({
  selector: 'app-ai-provider-settings',
  imports: [FormsModule, RouterLink],
  template: `<section class="ai-page">
    <header class="ai-header">
      <div>
        <h1>OpenAI-compatible provider</h1>
        <p>Credentials remain encrypted on the API server and are never returned here.</p>
      </div>
      <a routerLink="/settings/ai">Back to settings</a>
    </header>
    @if (loading()) {
      <p role="status">Loading provider configuration…</p>
    }
    @if (error()) {
      <p class="ai-error" role="alert">{{ error() }}</p>
    }
    @if (message()) {
      <p role="status">{{ message() }}</p>
    }
    @if (configuration(); as saved) {
      <article class="ai-card">
        <h2>Status: {{ statusLabel(saved) }}</h2>
        <p>
          Credential: {{ saved.masked_credential || 'Not configured' }} ·
          {{ sourceLabel(saved.credential_source) }}
        </p>
        <p>
          Validation: {{ saved.validation_status }} ·
          {{ saved.safe_validation_message || 'Not validated' }}
        </p>
        @if (saved.last_validated_at) {
          <p>
            Last checked {{ saved.last_validated_at }} · {{ saved.last_validation_latency_ms }} ms
          </p>
        }
      </article>
      <form class="ai-card ai-form" (ngSubmit)="save()">
        <label
          >API key
          <input
            type="password"
            name="apiKey"
            maxlength="4096"
            autocomplete="new-password"
            [(ngModel)]="apiKey"
            placeholder="Leave blank to keep the saved credential"
          />
        </label>
        <label
          >Base URL<input required maxlength="500" name="baseUrl" [(ngModel)]="form.base_url"
        /></label>
        <label
          >Default model<input
            required
            maxlength="120"
            name="model"
            list="provider-models"
            [(ngModel)]="form.default_model"
        /></label>
        <datalist id="provider-models">
          @for (model of models(); track model.identifier) {
            <option [value]="model.identifier"></option>
          }
        </datalist>
        <label
          >Timeout (seconds)<input
            type="number"
            min="10"
            max="120"
            name="timeout"
            [(ngModel)]="form.request_timeout_seconds"
        /></label>
        <label
          >Maximum attempts<input
            type="number"
            min="1"
            max="5"
            name="attempts"
            [(ngModel)]="form.max_retry_attempts"
        /></label>
        <label
          ><input type="checkbox" name="manual" [(ngModel)]="form.manual_model_allowed" /> Permit an
          explicitly entered model when discovery is unavailable</label
        >
        <label
          ><input type="checkbox" name="enabled" [(ngModel)]="form.enabled" /> Enable real
          provider</label
        >
        <label
          ><input type="checkbox" name="fallback" [(ngModel)]="fallbackEnabled" /> Explicitly allow
          fallback to deterministic mock</label
        >
        <div class="ai-actions">
          <button [disabled]="busy()">Save configuration</button>
          <button type="button" class="secondary" [disabled]="busy()" (click)="validate()">
            Validate configuration
          </button>
          <button type="button" class="secondary" [disabled]="busy()" (click)="discover()">
            Discover models
          </button>
          <button type="button" class="danger" [disabled]="busy()" (click)="remove()">
            Remove saved key
          </button>
        </div>
      </form>
    }
  </section>`,
  styleUrl: './ai.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AIProviderSettingsComponent implements OnInit {
  private readonly api = inject(AIService);
  readonly configuration = signal<AIProviderConfiguration | null>(null);
  readonly models = signal<AIModelSummary[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  apiKey = '';
  fallbackEnabled = false;
  form = {} as UpdateAIProviderConfiguration;

  ngOnInit(): void {
    void this.load();
  }
  async load(): Promise<void> {
    try {
      const value = await this.api.providerConfiguration();
      this.apply(value);
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    } finally {
      this.loading.set(false);
    }
  }
  async save(): Promise<void> {
    await this.act(async () => {
      const value = await this.api.saveProvider({
        ...this.form,
        api_key: this.apiKey || null,
        fallback_provider_key: this.fallbackEnabled ? 'deterministic_mock_v1' : null,
      });
      this.apiKey = '';
      this.apply(value);
      this.message.set('Provider configuration saved. Validate before production use.');
    });
  }
  async validate(): Promise<void> {
    await this.act(async () => {
      const value = await this.api.validateProvider();
      this.message.set(
        `${value.safe_message} Correlation ${value.correlation_id || 'unavailable'} · ${value.latency_ms} ms`,
      );
      this.apply(await this.api.providerConfiguration());
    });
  }
  async discover(): Promise<void> {
    await this.act(async () => {
      this.models.set(await this.api.models());
      this.message.set(`${this.models().length} model(s) discovered and cached.`);
    });
  }
  async remove(): Promise<void> {
    if (!confirm('Remove the application-stored provider credential?')) return;
    await this.act(async () => {
      this.apply(await this.api.removeCredential());
      this.apiKey = '';
      this.message.set('Application credential removed.');
    });
  }
  statusLabel(value: AIProviderConfiguration): string {
    if (!value.enabled) return 'Disabled';
    if (!value.configured) return 'Not configured';
    return value.validation_status === 'valid'
      ? 'Valid'
      : value.validation_status === 'invalid'
        ? 'Invalid'
        : 'Unknown';
  }
  sourceLabel(source: string): string {
    return (
      {
        application: 'Configured in application',
        deployment: 'Configured by deployment',
        not_configured: 'Not configured',
      }[source] ?? 'Unknown'
    );
  }
  private apply(value: AIProviderConfiguration): void {
    this.configuration.set(value);
    this.form = {
      base_url: value.base_url,
      default_model: value.default_model,
      manual_model_allowed: value.manual_model_allowed,
      enabled: value.enabled,
      fallback_provider_key: value.fallback_provider_key,
      request_timeout_seconds: value.request_timeout_seconds,
      max_retry_attempts: value.max_retry_attempts,
    };
    this.fallbackEnabled = value.fallback_provider_key === 'deterministic_mock_v1';
  }
  private async act(action: () => Promise<void>): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    try {
      await action();
    } catch (error) {
      this.error.set(AIService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}
