import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { PublishingSchedule } from '@vayujit/shared';
import { PublishingService } from './publishing.service';

type Frequency = 'daily' | 'weekly' | 'monthly';
type ResumePolicy = 'skip_missed' | 'next_occurrence' | 'one_catch_up';

@Component({
  selector: 'app-publishing-schedules',
  imports: [DatePipe, FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="op-page">
      <header>
        <p class="op-eyebrow">Publishing runtime</p>
        <h1>Schedules</h1>
      </header>
      <form class="op-card op-grid" (ngSubmit)="create()" aria-label="Create publishing schedule">
        <h2>Schedule approved content</h2>
        <label>Name<input name="name" required [(ngModel)]="draft.name" /></label>
        <label
          >Approved Artifact ID<input name="artifact" required [(ngModel)]="draft.artifact_id"
        /></label>
        <label
          >Destination ID<input name="destination" required [(ngModel)]="draft.destination_id"
        /></label>
        <label
          >Action
          <select name="action" [(ngModel)]="draft.requested_action">
            <option value="create_draft">Create draft</option>
            <option value="publish">Publish</option>
            <option value="update">Update WordPress</option>
            <option value="update_product">Update Shopify Product</option>
            <option value="activate_product">Activate Shopify Product</option>
            <option value="archive_product">Archive Shopify Product</option>
          </select>
        </label>
        @if (draft.requested_action === 'publish') {
          <p class="op-warning">This action will explicitly publish approved content remotely.</p>
        }
        @if (draft.requested_action === 'activate_product') {
          <p class="op-warning">Activation can make the Shopify Product publicly available.</p>
        }
        <label
          >Schedule type
          <select name="type" [(ngModel)]="draft.schedule_type" (ngModelChange)="preview()">
            <option value="one_time">One time</option>
            <option value="recurring">Recurring</option>
          </select>
        </label>
        <label
          >Local date and time<input
            name="time"
            required
            type="datetime-local"
            [(ngModel)]="draft.local_scheduled_at"
            (ngModelChange)="preview()"
        /></label>
        <label
          >IANA timezone<input
            name="timezone"
            required
            list="timezones"
            [(ngModel)]="draft.timezone_name"
            (ngModelChange)="preview()"
        /></label>
        <datalist id="timezones">
          <option value="UTC"></option>
          <option value="Asia/Kolkata"></option>
          <option value="America/New_York"></option>
          <option value="Europe/London"></option>
          <option value="Australia/Sydney"></option>
        </datalist>
        @if (draft.schedule_type === 'recurring') {
          <label
            >Recurrence
            <select name="frequency" [(ngModel)]="frequency" (ngModelChange)="preview()">
              <option value="daily">Daily</option>
              <option value="weekly">Weekly / selected weekdays</option>
              <option value="monthly">Monthly</option>
            </select>
          </label>
          @if (frequency === 'weekly') {
            <fieldset>
              <legend>Weekdays</legend>
              @for (day of weekdays; track day.value) {
                <label
                  ><input
                    type="checkbox"
                    [name]="'weekday-' + day.value"
                    [checked]="selectedWeekdays.includes(day.value)"
                    (change)="toggleWeekday(day.value)"
                  />{{ day.label }}</label
                >
              }
            </fieldset>
          }
          @if (frequency === 'monthly') {
            <label
              >Monthly day<input
                name="monthly-day"
                type="number"
                min="1"
                max="31"
                [(ngModel)]="monthlyDay"
                (ngModelChange)="preview()"
            /></label>
          }
          <label
            >Recurrence end<input
              name="recurrence-end"
              type="datetime-local"
              [(ngModel)]="recurrenceEnd"
          /></label>
          <label
            >Maximum occurrences<input
              name="occurrences"
              type="number"
              min="1"
              max="1000"
              [(ngModel)]="maxOccurrences"
          /></label>
        }
        <button type="button" class="op-button secondary" (click)="preview()">
          Preview occurrences
        </button>
        <button class="op-button" [disabled]="busy()">Create schedule</button>
        @if (message()) {
          <p role="status">{{ message() }}</p>
        }
        @if (previewError()) {
          <p class="op-error" role="alert">{{ previewError() }}</p>
        }
        @if (occurrences().length) {
          <section aria-label="Next occurrence preview">
            <h3>Next occurrences</h3>
            <ol>
              @for (item of occurrences(); track item.utc) {
                <li>
                  Local: {{ item.local | date: 'medium' }} {{ draft.timezone_name }}<br />
                  UTC: {{ item.utc | date: 'medium' : 'UTC' }}
                </li>
              }
            </ol>
          </section>
        }
      </form>
      <div class="op-card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Connector</th>
              <th>Next run</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            @for (item of schedules(); track item.id) {
              <tr>
                <td>{{ item.name }}</td>
                <td>{{ item.connector_key }}</td>
                <td>{{ item.next_run_at_utc | date: 'medium' }}</td>
                <td>{{ item.archived ? 'archived' : item.paused ? 'paused' : 'active' }}</td>
                <td>
                  @if (item.paused) {
                    <label
                      >Missed policy<select [(ngModel)]="resumePolicies[item.id]">
                        <option value="skip_missed">Skip missed</option>
                        <option value="next_occurrence">Next occurrence</option>
                        <option value="one_catch_up">Create one catch-up</option>
                      </select></label
                    >
                    <button class="op-button secondary" (click)="resume(item)">Resume</button>
                  } @else {
                    <button class="op-button secondary" (click)="pause(item)">Pause</button>
                  }
                  <a [routerLink]="['/publishing/schedules', item.id]">Details</a>
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="5">No schedules yet.</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </section>
  `,
})
export class SchedulesComponent implements OnInit {
  private readonly publishing = inject(PublishingService);
  readonly schedules = signal<PublishingSchedule[]>([]);
  readonly busy = signal(false);
  readonly message = signal('');
  readonly previewError = signal('');
  readonly occurrences = signal<{ local: string; utc: string }[]>([]);
  readonly weekdays = [
    { label: 'Monday', value: 0 },
    { label: 'Tuesday', value: 1 },
    { label: 'Wednesday', value: 2 },
    { label: 'Thursday', value: 3 },
    { label: 'Friday', value: 4 },
    { label: 'Saturday', value: 5 },
    { label: 'Sunday', value: 6 },
  ];
  selectedWeekdays: number[] = [];
  frequency: Frequency = 'daily';
  monthlyDay = 1;
  recurrenceEnd = '';
  maxOccurrences = 100;
  resumePolicies: Record<string, ResumePolicy> = {};
  draft = {
    name: '',
    artifact_id: '',
    destination_id: '',
    requested_action: 'publish',
    local_scheduled_at: '',
    timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
    schedule_type: 'one_time' as 'one_time' | 'recurring',
  };
  ngOnInit() {
    void this.load();
  }
  recurrence(): Record<string, unknown> | undefined {
    if (this.draft.schedule_type !== 'recurring') return undefined;
    return {
      frequency: this.frequency,
      interval: 1,
      weekdays: this.frequency === 'weekly' ? this.selectedWeekdays : [],
      day_of_month: this.frequency === 'monthly' ? this.monthlyDay : null,
      fold: 0,
    };
  }
  toggleWeekday(value: number) {
    this.selectedWeekdays = this.selectedWeekdays.includes(value)
      ? this.selectedWeekdays.filter((item) => item !== value)
      : [...this.selectedWeekdays, value].sort();
    void this.preview();
  }
  async load() {
    this.schedules.set((await this.publishing.schedules()).items);
  }
  async preview() {
    if (!this.draft.local_scheduled_at || !this.draft.timezone_name) return;
    try {
      const result = await this.publishing.previewSchedule({
        local_scheduled_at: this.draft.local_scheduled_at,
        timezone_name: this.draft.timezone_name,
        schedule_type: this.draft.schedule_type,
        recurrence: this.recurrence(),
        count: 5,
      });
      this.occurrences.set(result.occurrences);
      this.previewError.set(result.dst_warning || '');
    } catch (error) {
      this.occurrences.set([]);
      this.previewError.set(PublishingService.errorMessage(error));
    }
  }
  async create() {
    this.busy.set(true);
    this.message.set('');
    try {
      await this.publishing.createSchedule({
        ...this.draft,
        recurrence: this.recurrence(),
        recurrence_end_at: this.recurrenceEnd || undefined,
        max_occurrences: this.maxOccurrences,
      });
      this.message.set('Schedule created.');
      await this.load();
    } catch (error) {
      this.message.set(PublishingService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  async pause(item: PublishingSchedule) {
    await this.publishing.scheduleAction(item.id, 'pause');
    await this.load();
  }
  async resume(item: PublishingSchedule) {
    await this.publishing.scheduleAction(
      item.id,
      'resume',
      this.resumePolicies[item.id] || 'next_occurrence',
    );
    await this.load();
  }
}
