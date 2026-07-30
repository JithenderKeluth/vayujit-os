import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { Campaign } from '@vayujit/shared';
import { CampaignService } from './campaign.service';

@Component({
  selector: 'app-campaign-list',
  imports: [DatePipe, RouterLink],
  template: `
    <section class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Orchestration</p>
          <h1>Campaigns</h1>
        </div>
        <div class="actions">
          <a class="button" routerLink="/calendar">Content calendar</a>
          <a class="button primary" routerLink="/campaigns/new">Create Campaign</a>
        </div>
      </header>
      @if (loading()) {
        <p aria-live="polite">Loading Campaigns…</p>
      } @else if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      } @else if (!campaigns().length) {
        <div class="panel">
          <h2>No Campaigns yet</h2>
          <p>Create a Campaign to organize approved content.</p>
        </div>
      } @else {
        <div class="grid">
          @for (campaign of campaigns(); track campaign.id) {
            <article class="card">
              <span class="badge">{{ campaign.status }}</span>
              <h2>
                <a [routerLink]="['/campaigns', campaign.id]">{{ campaign.name }}</a>
              </h2>
              <p>{{ campaign.objective || 'No objective provided.' }}</p>
              <p>
                {{ campaign.start_at_utc | date: 'medium' }} –
                {{ campaign.end_at_utc | date: 'medium' }}
              </p>
              <small>{{ campaign.timezone_name }}</small>
            </article>
          }
        </div>
      }
    </section>
  `,
  styleUrl: './campaigns.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CampaignListComponent {
  private readonly api = inject(CampaignService);
  readonly campaigns = signal<Campaign[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');
  constructor() {
    void this.load();
  }
  private async load(): Promise<void> {
    try {
      this.campaigns.set(await this.api.list());
    } catch {
      this.error.set('Campaigns could not be loaded.');
    } finally {
      this.loading.set(false);
    }
  }
}
