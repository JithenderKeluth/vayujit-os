import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { CampaignCalendarEvent } from '@vayujit/shared';
import { CampaignService } from './campaign.service';

@Component({
  selector: 'app-content-calendar',
  imports: [DatePipe, FormsModule, RouterLink],
  template: `
    <section class="page">
      <header class="page-header">
        <div>
          <p class="eyebrow">Content operations</p>
          <h1>Content Calendar</h1>
        </div>
        <a routerLink="/campaigns">Campaigns</a>
      </header>
      <nav class="calendar-nav" aria-label="Calendar view">
        <div role="group" aria-label="View">
          <button (click)="view.set('month')">Month</button
          ><button (click)="view.set('week')">Week</button
          ><button (click)="view.set('agenda')">Agenda</button>
        </div>
        <label
          >Connector<select [(ngModel)]="connector">
            <option value="">All</option>
            <option value="wordpress">WordPress</option>
            <option value="shopify">Shopify</option>
          </select></label
        >
        <button (click)="previous()" aria-label="Previous period">Previous</button
        ><button (click)="next()" aria-label="Next period">Next</button>
      </nav>
      <p aria-live="polite">
        {{ start() | date: 'mediumDate' }} – {{ end() | date: 'mediumDate' }} · {{ view() }} view
      </p>
      @if (loading()) {
        <p>Loading calendar…</p>
      } @else if (!filtered().length) {
        <div class="panel"><h2>No scheduled Campaign activities</h2></div>
      }
      <div class="calendar-grid" role="list" aria-label="Campaign activities">
        @for (event of filtered(); track event.activity_id) {
          <article
            role="listitem"
            class="calendar-event"
            [class.conflict]="event.has_conflict"
            tabindex="0"
          >
            <time [attr.datetime]="event.scheduled_at_utc">{{
              event.scheduled_at_utc | date: 'medium'
            }}</time>
            <h2>
              <a [routerLink]="['/campaigns', event.campaign_id]">{{ event.activity_name }}</a>
            </h2>
            <p>
              {{ event.campaign_name }} · {{ event.connector_key || 'checkpoint' }} ·
              {{ event.requested_action || 'review' }}
            </p>
            <span class="badge">{{ event.status }}</span> <span>{{ event.readiness_status }}</span>
            @if (event.has_conflict) {
              <strong class="error">Conflict requires review</strong>
            }
          </article>
        }
      </div>
    </section>
  `,
  styleUrl: './campaigns.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ContentCalendarComponent {
  private readonly api = inject(CampaignService);
  readonly events = signal<CampaignCalendarEvent[]>([]);
  readonly loading = signal(true);
  readonly view = signal<'month' | 'week' | 'agenda'>('month');
  readonly start = signal(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  readonly end = signal(new Date(new Date().getFullYear(), new Date().getMonth() + 1, 1));
  connector = '';
  constructor() {
    void this.load();
  }
  filtered(): CampaignCalendarEvent[] {
    return this.events().filter((item) => !this.connector || item.connector_key === this.connector);
  }
  previous(): void {
    const value = this.start();
    this.start.set(new Date(value.getFullYear(), value.getMonth() - 1, 1));
    this.end.set(new Date(value.getFullYear(), value.getMonth(), 1));
    void this.load();
  }
  next(): void {
    const value = this.start();
    this.start.set(new Date(value.getFullYear(), value.getMonth() + 1, 1));
    this.end.set(new Date(value.getFullYear(), value.getMonth() + 2, 1));
    void this.load();
  }
  private async load(): Promise<void> {
    this.loading.set(true);
    this.events.set(await this.api.calendar(this.start().toISOString(), this.end().toISOString()));
    this.loading.set(false);
  }
}
