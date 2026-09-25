import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';

interface ProviderSummary {
  provider_id: string;
  display_name: string;
  category: string;
  capabilities: string[];
  environments: string[];
  configuration_status: string;
  credential_status: string;
  connectivity_status: string;
  provider_status: string;
  live_capable: boolean;
}

@Component({
  selector: 'app-provider-settings',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="settings-page">
      <header class="settings-header">
        <div>
          <h1>Provider integrations</h1>
          <p>Review provider capabilities and environment readiness without exposing secrets.</p>
        </div>
        <a routerLink="/settings">Back to settings</a>
      </header>
      @if (loading()) {
        <p role="status">Loading provider registry…</p>
      }
      @if (error()) {
        <p role="alert" class="settings-error">{{ error() }}</p>
      }
      <div class="provider-grid">
        @for (provider of providers(); track provider.provider_id) {
          <article class="provider-card">
            <div class="provider-card__header">
              <div>
                <h2>{{ provider.display_name }}</h2>
                <p>{{ provider.category }} · {{ provider.provider_id }}</p>
              </div>
              <span class="provider-status">{{ provider.provider_status }}</span>
            </div>
            <dl>
              <div>
                <dt>Environment</dt>
                <dd>{{ provider.environments.join(', ') }}</dd>
              </div>
              <div>
                <dt>Configuration</dt>
                <dd>{{ provider.configuration_status }}</dd>
              </div>
              <div>
                <dt>Credentials</dt>
                <dd>{{ provider.credential_status }}</dd>
              </div>
              <div>
                <dt>Connectivity</dt>
                <dd>{{ provider.connectivity_status }}</dd>
              </div>
            </dl>
            <p class="provider-capabilities">
              Capabilities: {{ provider.capabilities.join(', ') }}
            </p>
            @if (!provider.live_capable) {
              <p class="provider-note">Live validation is not enabled for this provider in 14A.</p>
            }
          </article>
        }
      </div>
    </section>
  `,
  styles: [
    `
      .settings-page {
        max-width: 1180px;
        margin: 0 auto;
        padding: 2rem;
      }
      .settings-header {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: start;
      }
      .settings-header h1 {
        margin: 0;
      }
      .settings-header p {
        color: #536b80;
      }
      .settings-error {
        color: #9c1c1c;
        background: #fff0f0;
        padding: 1rem;
      }
      .provider-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 1rem;
        margin-top: 1.5rem;
      }
      .provider-card {
        border: 1px solid #cbd8e1;
        border-radius: 12px;
        padding: 1.25rem;
        background: #fff;
      }
      .provider-card__header {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
      }
      .provider-card h2 {
        margin: 0;
        font-size: 1.15rem;
      }
      .provider-card p {
        color: #536b80;
      }
      .provider-status {
        font-size: 0.8rem;
        font-weight: 700;
      }
      dl {
        display: grid;
        gap: 0.5rem;
      }
      dl div {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
      }
      dt {
        color: #536b80;
      }
      dd {
        margin: 0;
        text-align: right;
      }
      .provider-capabilities {
        font-size: 0.85rem;
      }
      .provider-note {
        font-size: 0.85rem;
      }
      @media (max-width: 600px) {
        .settings-page {
          padding: 1rem;
        }
        .settings-header {
          display: block;
        }
      }
    `,
  ],
})
export class ProviderSettingsComponent implements OnInit {
  private readonly http = inject(HttpClient);
  readonly providers = signal<ProviderSummary[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');

  ngOnInit(): void {
    void this.load();
  }

  private async load(): Promise<void> {
    try {
      const response = await firstValueFrom(
        this.http.get<ProviderSummary[]>(`${environment.apiUrl}/providers`, {
          withCredentials: true,
        }),
      );
      this.providers.set(response);
    } catch {
      this.error.set('Provider registry is unavailable. Check the authenticated API connection.');
    } finally {
      this.loading.set(false);
    }
  }
}
