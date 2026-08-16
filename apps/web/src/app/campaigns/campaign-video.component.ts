import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type { CampaignActivity } from '@vayujit/shared';
import { CampaignService } from './campaign.service';

@Component({
  selector: 'app-campaign-video',
  imports: [DatePipe, RouterLink],
  template: `
    <section class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Campaign Video</p>
          <h1>{{ campaignName() || 'Campaign Video orchestration' }}</h1>
          <p>
            Exact approved Video versions flow through Campaign dependencies and durable execution.
          </p>
        </div>
        <a class="button" [routerLink]="['/campaigns', campaignId]">Back to Campaign</a>
      </header>
      @if (error()) {
        <p class="error" role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p aria-live="polite">Loading Campaign Video…</p>
      }
      @if (overview(); as state) {
        <section class="grid" aria-label="Campaign Video summary">
          <article class="panel">
            <h2>Video Activities</h2>
            <strong>{{ state['video_activity_count'] }}</strong>
          </article>
          @for (entry of countEntries(); track entry[0]) {
            <article class="panel">
              <h2>{{ entry[0] }}</h2>
              <strong>{{ entry[1] }}</strong>
            </article>
          }
        </section>
      }
      <section class="panel">
        <h2>Exact Video Activities</h2>
        @if (!activities().length) {
          <p>No Video Activities yet. Use the Campaign Activity editor to add one.</p>
        }
        <div class="grid">
          @for (activity of activities(); track activity.id) {
            <article class="card">
              <span class="badge">{{ activity.status }}</span>
              <h3>{{ activity.name }}</h3>
              <p>
                {{ activity.video_channel || 'Video' }} · version
                {{ activity.video_version || '—' }}
              </p>
              <p>
                Scheduled {{ activity.scheduled_at_utc | date: 'medium' }} ·
                {{ activity.timezone_name }}
              </p>
              <p>Dependency: {{ activity.dependency_state || activity.readiness_status }}</p>
              <p class="op-muted">Output: {{ activity.video_output_id || '—' }}</p>
              <a class="button" [routerLink]="['/campaigns', campaignId, 'video', activity.id]"
                >Open detail</a
              >
            </article>
          }
        </div>
      </section>
    </section>
  `,
  styleUrl: './campaigns.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CampaignVideoComponent {
  private readonly api = inject(CampaignService);
  readonly campaignId = inject(ActivatedRoute).snapshot.paramMap.get('id')!;
  readonly loading = signal(true);
  readonly error = signal('');
  readonly campaignName = signal('');
  readonly overview = signal<Record<string, unknown> | null>(null);
  readonly activities = signal<CampaignActivity[]>([]);

  constructor() {
    void this.load();
  }

  countEntries(): Array<[string, number]> {
    const counts = this.overview()?.['counts'];
    return counts && typeof counts === 'object'
      ? Object.entries(counts as Record<string, number>)
      : [];
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      const [campaign, activities, overview] = await Promise.all([
        this.api.get(this.campaignId),
        this.api.activities(this.campaignId),
        this.api.videoOverview(this.campaignId),
      ]);
      this.campaignName.set(campaign.name);
      this.activities.set(
        activities.filter((activity) => activity.activity_type === 'video_campaign'),
      );
      this.overview.set(overview);
    } catch {
      this.error.set('Campaign Video data is unavailable. Check the authenticated API connection.');
    } finally {
      this.loading.set(false);
    }
  }
}
