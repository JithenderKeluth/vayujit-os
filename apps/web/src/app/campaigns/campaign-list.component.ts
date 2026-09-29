import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { Campaign } from '@vayujit/shared';
import { GrowthJourneyNavComponent } from '../shared/growth-journey-nav.component';
import { PageHeaderComponent } from '../shared/page-header.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from '../shared/state-components';
import { CampaignService } from './campaign.service';

@Component({
  selector: 'app-campaign-list',
  imports: [
    DatePipe,
    RouterLink,
    GrowthJourneyNavComponent,
    PageHeaderComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    LoadingStateComponent,
  ],
  template: `
    <section class="page">
      <app-growth-journey-nav current="campaigns" />
      <app-page-header
        eyebrow="Grow / campaigns"
        title="Campaigns"
        description="Organize approved content into reviewable campaign work."
      >
        <div page-header-actions class="actions">
          <a class="button" routerLink="/calendar">Content calendar</a>
          <a class="button primary" routerLink="/campaigns/new">Create campaign</a>
        </div>
      </app-page-header>
      @if (loading()) {
        <app-loading-state message="Loading campaigns..." />
      } @else if (error()) {
        <app-error-state
          title="Campaigns are unavailable"
          [message]="error()"
          retryLabel="Retry"
          (retry)="load()"
        />
      } @else if (!campaigns().length) {
        <app-empty-state
          title="No campaigns yet"
          message="Create a campaign to organize approved content."
        />
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
                {{ campaign.start_at_utc | date: 'medium' }} -
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
  async load(): Promise<void> {
    try {
      this.campaigns.set(await this.api.list());
    } catch {
      this.error.set('Campaigns could not be loaded.');
    } finally {
      this.loading.set(false);
    }
  }
}
