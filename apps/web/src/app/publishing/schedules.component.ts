import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { PublishingSchedule } from '@vayujit/shared';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-publishing-schedules',
  imports: [DatePipe, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: ` <section class="op-page">
    <header>
      <p class="op-eyebrow">Publishing runtime</p>
      <h1>Schedules</h1>
    </header>
    <form class="op-card op-grid" (ngSubmit)="create()">
      <h2>Schedule approved content</h2>
      <label>Name<input name="name" required [(ngModel)]="draft.name" /></label>
      <label
        >Approved artifact ID<input name="artifact" required [(ngModel)]="draft.artifact_id"
      /></label>
      <label
        >Destination ID<input name="destination" required [(ngModel)]="draft.destination_id"
      /></label>
      <label
        >Local time<input
          name="time"
          required
          type="datetime-local"
          [(ngModel)]="draft.local_scheduled_at"
      /></label>
      <label>Timezone<input name="timezone" required [(ngModel)]="draft.timezone_name" /></label>
      <button class="op-button" [disabled]="busy()">Create schedule</button>
      @if (message()) {
        <p role="status">{{ message() }}</p>
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
            <th></th>
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
                <button class="op-button secondary" (click)="toggle(item)">
                  {{ item.paused ? 'Resume' : 'Pause' }}
                </button>
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
  </section>`,
})
export class SchedulesComponent implements OnInit {
  private readonly publishing = inject(PublishingService);
  readonly schedules = signal<PublishingSchedule[]>([]);
  readonly busy = signal(false);
  readonly message = signal('');
  draft = {
    name: '',
    artifact_id: '',
    destination_id: '',
    requested_action: 'publish',
    local_scheduled_at: '',
    timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
    schedule_type: 'one_time' as const,
  };
  ngOnInit() {
    void this.load();
  }
  async load() {
    this.schedules.set((await this.publishing.schedules()).items);
  }
  async create() {
    this.busy.set(true);
    this.message.set('');
    try {
      await this.publishing.createSchedule(this.draft);
      this.message.set('Schedule created.');
      await this.load();
    } catch (error) {
      this.message.set(PublishingService.errorMessage(error));
    } finally {
      this.busy.set(false);
    }
  }
  async toggle(item: PublishingSchedule) {
    await this.publishing.scheduleAction(item.id, item.paused ? 'resume' : 'pause');
    await this.load();
  }
}
