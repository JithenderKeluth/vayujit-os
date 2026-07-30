import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { WordPressConnectorConfiguration } from '@vayujit/shared';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-wordpress-settings',
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section class="pub-page">
      <header class="pub-header">
        <div>
          <p class="pub-eyebrow">Publishing connector</p>
          <h1>WordPress</h1>
          <p>Connect with a WordPress application password. Secrets are never displayed again.</p>
        </div>
        <a routerLink="/publishing">Back to Publishing</a>
      </header>

      @if (message()) {
        <p class="pub-notice" role="status">{{ message() }}</p>
      }
      @if (error()) {
        <p class="pub-error" role="alert">{{ error() }}</p>
      }

      <form class="pub-card pub-form" (ngSubmit)="save()">
        <label>
          Site URL
          <input
            name="siteUrl"
            [(ngModel)]="form.site_url"
            placeholder="https://example.com"
            required
          />
        </label>
        <label>
          Username
          <input name="username" [(ngModel)]="form.username" autocomplete="username" required />
        </label>
        <label>
          Application password
          <input
            name="applicationPassword"
            [(ngModel)]="form.application_password"
            type="password"
            autocomplete="new-password"
            [placeholder]="configuration()?.configured ? 'Leave blank to keep existing' : ''"
          />
        </label>
        <label>
          Default post status
          <select name="postStatus" [(ngModel)]="form.default_post_status">
            <option value="draft">Draft</option>
            <option value="publish">Publish</option>
          </select>
        </label>
        <label>
          Request timeout (seconds)
          <input
            name="timeout"
            [(ngModel)]="form.request_timeout_seconds"
            type="number"
            min="10"
            max="120"
          />
        </label>
        <label>
          Retry attempts
          <input
            name="retries"
            [(ngModel)]="form.max_retry_attempts"
            type="number"
            min="1"
            max="5"
          />
        </label>
        <button class="pub-button" type="submit" [disabled]="busy()">Save configuration</button>
      </form>

      @if (configuration(); as config) {
        <section class="pub-card">
          <h2>Connection state</h2>
          <dl>
            <dt>Credential</dt>
            <dd>
              {{ config.credential_source }} · {{ config.masked_username || 'not configured' }}
            </dd>
            <dt>Validation</dt>
            <dd>
              {{ config.validation_status }} · {{ config.safe_validation_message || 'Not run' }}
            </dd>
            <dt>Connector</dt>
            <dd>{{ config.enabled ? 'Enabled' : 'Disabled' }}</dd>
          </dl>
          <div class="pub-actions">
            <button type="button" (click)="validate()" [disabled]="busy()">Validate</button>
            <button
              type="button"
              (click)="toggle(config.enabled ? 'disable' : 'enable')"
              [disabled]="busy()"
            >
              {{ config.enabled ? 'Disable' : 'Enable' }}
            </button>
            <button type="button" (click)="removeCredential()" [disabled]="busy()">
              Remove application credential
            </button>
          </div>
        </section>
      }
    </section>
  `,
  styleUrl: './publishing.css',
})
export class WordPressSettingsComponent implements OnInit {
  private readonly api = inject(PublishingService);
  readonly configuration = signal<WordPressConnectorConfiguration | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  form = {
    site_url: '',
    username: '',
    application_password: '',
    enabled: false,
    default_post_status: 'draft' as 'draft' | 'publish',
    request_timeout_seconds: 45,
    max_retry_attempts: 3,
  };

  ngOnInit(): void {
    void this.load();
  }

  private async load() {
    try {
      const value = await this.api.wordpressConfiguration();
      this.configuration.set(value);
      this.form.site_url = value.site_url;
      this.form.default_post_status = value.default_post_status;
      this.form.request_timeout_seconds = value.request_timeout_seconds;
      this.form.max_retry_attempts = value.max_retry_attempts;
      this.form.enabled = value.enabled;
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    }
  }

  async save() {
    await this.run(async () => {
      const payload = { ...this.form };
      if (!payload.application_password)
        delete (payload as { application_password?: string }).application_password;
      const value = await this.api.saveWordpressConfiguration(payload);
      this.form.application_password = '';
      this.configuration.set(value);
      this.message.set('WordPress configuration saved. Validate it before enabling.');
    });
  }

  async validate() {
    await this.run(async () => {
      const result = await this.api.validateWordpress();
      await this.load();
      this.message.set(result.safe_message);
    });
  }

  async toggle(action: 'enable' | 'disable') {
    await this.run(async () => {
      this.configuration.set(await this.api.setWordpressEnabled(action));
      this.message.set(`WordPress ${action}d.`);
    });
  }

  async removeCredential() {
    if (!confirm('Remove the stored WordPress application password and disable the connector?'))
      return;
    await this.run(async () => {
      this.configuration.set(await this.api.removeWordpressCredential());
      this.message.set('Application credential removed.');
    });
  }

  private async run(operation: () => Promise<void>) {
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    try {
      await operation();
    } catch (error) {
      this.error.set(PublishingService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
}
