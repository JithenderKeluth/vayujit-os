import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

type AdsOverview = {
  accounts: Array<{ provider: string; display_name: string; status: string; enabled: boolean }>;
  campaigns: Array<{
    id: string;
    provider: string;
    name: string;
    state: string;
    remote_campaign_id?: string;
  }>;
  active_campaigns: number;
  paused: number;
  failed: number;
  synthetic: boolean;
  attention_items: string[];
};

@Component({
  selector: 'app-ads-workspace',
  standalone: true,
  imports: [RouterLink],
  template: `
    <section class="ads-workspace" aria-labelledby="ads-title">
      <header class="ads-header">
        <div>
          <p class="eyebrow">Ads &amp; Marketing Automation</p>
          <h1 id="ads-title">Normalized Ads workspace</h1>
          <p>One owner-scoped foundation for Meta and Google local fake connectors.</p>
        </div>
        <span class="synthetic-badge" aria-label="Synthetic local data"
          >Synthetic · local only</span
        >
      </header>
      <nav aria-label="Ads workspace">
        <a routerLink="/ads">Overview</a><a routerLink="/ads/accounts">Accounts</a
        ><a routerLink="/ads/campaigns">Campaigns</a><a routerLink="/ads/analytics">Analytics</a
        ><a routerLink="/ads/recovery">Recovery</a><a routerLink="/ads/settings">Settings</a>
      </nav>
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p aria-live="polite">Loading Ads data…</p>
      }
      @if (!loading() && overview(); as value) {
        <div class="cards">
          <article>
            <h2>Accounts</h2>
            <strong>{{ value.accounts.length }}</strong>
          </article>
          <article>
            <h2>Active campaigns</h2>
            <strong>{{ value.active_campaigns }}</strong>
          </article>
          <article>
            <h2>Paused</h2>
            <strong>{{ value.paused }}</strong>
          </article>
          <article>
            <h2>Failed</h2>
            <strong>{{ value.failed }}</strong>
          </article>
        </div>
        <section class="panel">
          <h2>Accounts</h2>
          <ul>
            @for (account of value.accounts; track account.display_name) {
              <li>
                <strong>{{ account.display_name }}</strong> · {{ account.provider }} ·
                {{ account.status }} · {{ account.enabled ? 'Enabled' : 'Disabled' }}
              </li>
            } @empty {
              <li>No Ads accounts configured.</li>
            }
          </ul>
        </section>
        <section class="panel">
          <h2>Campaigns</h2>
          <ul>
            @for (campaign of value.campaigns; track campaign.id) {
              <li>
                <strong>{{ campaign.name }}</strong> · {{ campaign.provider }} ·
                {{ campaign.state }} · {{ campaign.remote_campaign_id || 'Local draft' }}
              </li>
            } @empty {
              <li>No Ads campaigns yet.</li>
            }
          </ul>
        </section>
        <aside class="attention">
          <strong>Local boundary:</strong> {{ value.attention_items.join(' ') }}
        </aside>
      }
    </section>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .ads-workspace {
        padding: 2rem;
        max-width: 1100px;
        margin: auto;
      }
      .ads-header {
        display: flex;
        justify-content: space-between;
        gap: 2rem;
        align-items: flex-start;
      }
      .eyebrow {
        font-size: 0.8rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
      }
      .synthetic-badge {
        border: 1px solid #16627a;
        border-radius: 999px;
        padding: 0.55rem 0.8rem;
        color: #16627a;
        font-weight: 700;
      }
      .ads-workspace nav {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        margin: 2rem 0;
      }
      .cards {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
      }
      .cards article,
      .panel,
      .attention {
        border: 1px solid #cad8dd;
        border-radius: 12px;
        background: #fff;
        padding: 1rem;
        margin-top: 1rem;
      }
      .cards strong {
        font-size: 2rem;
      }
      .panel ul {
        padding-left: 1.2rem;
      }
      .error {
        color: #9d1c27;
        background: #fff0f1;
        padding: 1rem;
      }
      .attention {
        background: #eef8fb;
      }
      @media (max-width: 768px) {
        .ads-header {
          display: block;
        }
        .cards {
          grid-template-columns: repeat(2, 1fr);
        }
      }
      @media (max-width: 390px) {
        .ads-workspace {
          padding: 1rem;
        }
        .cards {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class AdsWorkspaceComponent {
  private readonly http = inject(HttpClient);
  readonly overview = signal<AdsOverview | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  constructor() {
    void this.load();
  }
  private async load(): Promise<void> {
    try {
      this.overview.set(await firstValueFrom(this.http.get<AdsOverview>('/api/v1/ads/overview')));
    } catch {
      this.error.set('Ads data is unavailable. Check the authenticated API connection.');
    } finally {
      this.loading.set(false);
    }
  }
}
