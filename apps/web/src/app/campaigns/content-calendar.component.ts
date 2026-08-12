import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { CampaignCalendar, CampaignCalendarEvent } from '@vayujit/shared';
import { CampaignService } from './campaign.service';
import { SocialCalendarEvent, SocialService } from '../social/social.service';

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
          <button (click)="setView('month')">Month</button
          ><button (click)="setView('week')">Week</button
          ><button (click)="setView('agenda')">Agenda</button>
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
        <label
          >Social platform<select [(ngModel)]="socialPlatform" (ngModelChange)="loadSocial()">
            <option value="">All</option>
            <option value="instagram">Instagram</option>
            <option value="facebook">Facebook</option>
            <option value="youtube">YouTube</option>
          </select></label
        >
      </nav>
      <section class="panel" aria-labelledby="social-calendar-title">
        <h2 id="social-calendar-title">Social publishing</h2>
        @if (!socialEvents().length) {
          <p>No Social posts are scheduled in this period.</p>
        } @else {
          <div class="calendar-social-list" role="list">
            @for (event of socialEvents(); track event.id) {
              <article role="listitem" class="calendar-event">
                <time [attr.datetime]="event.scheduled_at_utc">{{
                  event.scheduled_at_utc | date: 'medium'
                }}</time>
                <strong>{{ event.platform }} / {{ event.content_type }}</strong>
                <span
                  >{{ event.status }} ? {{ event.timezone || 'UTC' }} ? v{{
                    event.artifact_version
                  }}</span
                >
                @if (event.failure_code) {
                  <span class="error">{{ event.failure_code }}</span>
                }
              </article>
            }
          </div>
        }
      </section>
      <p aria-live="polite">
        {{ start() | date: 'mediumDate' }} – {{ end() | date: 'mediumDate' }} · {{ view() }} view
      </p>
      @if (loading()) {
        <p>Loading calendar…</p>
      } @else if (!filtered().length) {
        <div class="panel"><h2>No scheduled Campaign activities</h2></div>
      }
      @if (projection()?.view === 'month') {
        <div class="calendar-grid month-grid" role="grid" aria-label="Month calendar">
          @for (day of monthDays(); track day.date) {
            <section role="gridcell" tabindex="0">
              <h2>{{ day.date | date: 'd' }}</h2>
              <p>{{ day.activity_count }} activities · {{ day.campaign_count }} campaigns</p>
              @if (day.conflict_count) {
                <strong class="error">{{ day.conflict_count }} conflicts</strong>
              }
              @for (event of day.previews; track event.activity_id) {
                <a [routerLink]="['/campaigns', event.campaign_id]">{{ event.activity_name }}</a>
              }
              @if (day.overflow_count) {
                <span>+{{ day.overflow_count }} more</span>
              }
            </section>
          }
        </div>
      } @else if (projection()?.view === 'week') {
        <div class="calendar-grid week-grid" role="grid" aria-label="Week calendar">
          @for (slot of weekSlots(); track slot.date) {
            <section role="gridcell">
              <h2>{{ slot.date | date: 'EEE d' }}</h2>
              <p>{{ slot.overlap_count }} overlaps</p>
              @for (event of slot.events; track event.activity_id) {
                <article tabindex="0">
                  <time>{{ event.scheduled_at_utc | date: 'shortTime' }}</time>
                  {{ event.activity_name }}
                </article>
              }
            </section>
          }
        </div>
      } @else {
        <div class="calendar-grid agenda-list" role="list" aria-label="Campaign agenda">
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
              <span class="badge">{{ event.status }}</span>
              <span>{{ event.readiness_status }}</span>
              @if (event.has_conflict) {
                <strong class="error">Conflict requires review</strong>
              }
            </article>
          }
        </div>
      }
    </section>
  `,
  styleUrl: './campaigns.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ContentCalendarComponent {
  private readonly api = inject(CampaignService);
  private readonly social = inject(SocialService);
  readonly events = signal<CampaignCalendarEvent[]>([]);
  readonly socialEvents = signal<SocialCalendarEvent[]>([]);
  readonly projection = signal<CampaignCalendar | null>(null);
  readonly loading = signal(true);
  readonly view = signal<'month' | 'week' | 'agenda'>('month');
  readonly start = signal(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  readonly end = signal(new Date(new Date().getFullYear(), new Date().getMonth() + 1, 1));
  connector = '';
  socialPlatform = '';
  constructor() {
    void this.load();
  }
  filtered(): CampaignCalendarEvent[] {
    return this.events().filter((item) => !this.connector || item.connector_key === this.connector);
  }
  monthDays() {
    const value = this.projection();
    return value?.view === 'month' ? value.days : [];
  }
  weekSlots() {
    const value = this.projection();
    return value?.view === 'week' ? value.slots : [];
  }
  setView(value: 'month' | 'week' | 'agenda'): void {
    this.view.set(value);
    void this.load();
  }
  previous(): void {
    const value = this.start();
    this.start.set(new Date(value.getFullYear(), value.getMonth() - 1, 1));
    this.end.set(new Date(value.getFullYear(), value.getMonth(), 1));
    void this.load();
  }
  loadSocial(): void {
    const params: Record<string, string> = {
      start: this.start().toISOString(),
      end: this.end().toISOString(),
    };
    if (this.socialPlatform) params['platform'] = this.socialPlatform;
    void this.social
      .calendar(params)
      .then((events) => this.socialEvents.set(events))
      .catch(() => this.socialEvents.set([]));
  }
  next(): void {
    const value = this.start();
    this.start.set(new Date(value.getFullYear(), value.getMonth() + 1, 1));
    this.end.set(new Date(value.getFullYear(), value.getMonth() + 2, 1));
    void this.load();
    this.loadSocial();
  }
  private async load(): Promise<void> {
    this.loading.set(true);
    const result = await this.api.calendar(
      this.start().toISOString(),
      this.end().toISOString(),
      this.view(),
    );
    this.projection.set(result);
    this.events.set(
      result.view === 'month'
        ? result.days.flatMap((day) => day.previews)
        : result.view === 'week'
          ? result.slots.flatMap((slot) => slot.events)
          : result.days.flatMap((day) => day.events),
    );
    this.loading.set(false);
    this.loadSocial();
  }
}
