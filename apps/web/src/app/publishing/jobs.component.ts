import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import type { PublishingJob } from '@vayujit/shared';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-publishing-jobs',
  imports: [DatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section class="op-page">
    <header>
      <p class="op-eyebrow">Publishing runtime</p>
      <h1>Jobs</h1>
    </header>
    <div class="op-card">
      <table>
        <thead>
          <tr>
            <th>Scheduled</th>
            <th>Connector</th>
            <th>Action</th>
            <th>State</th>
            <th>Attempts</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (item of jobs(); track item.id) {
            <tr>
              <td>{{ item.scheduled_at_utc | date: 'medium' }}</td>
              <td>{{ item.connector_key }}</td>
              <td>{{ item.requested_action }}</td>
              <td>{{ item.state }}</td>
              <td>{{ item.execution_attempt_count }} / {{ item.max_execution_attempts }}</td>
              <td>
                @if (['failed', 'dead_letter', 'cancelled', 'expired'].includes(item.state)) {
                  <button class="op-button secondary" (click)="act(item, 'retry')">Retry</button>
                }
                @if (
                  !['succeeded', 'failed', 'dead_letter', 'cancelled', 'expired'].includes(
                    item.state
                  )
                ) {
                  <button class="op-button danger" (click)="act(item, 'cancel')">Cancel</button>
                }
              </td>
            </tr>
          } @empty {
            <tr>
              <td colspan="6">No jobs yet.</td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  </section>`,
})
export class JobsComponent implements OnInit {
  private readonly publishing = inject(PublishingService);
  readonly jobs = signal<PublishingJob[]>([]);
  ngOnInit() {
    void this.load();
  }
  async load() {
    this.jobs.set((await this.publishing.jobs()).items);
  }
  async act(item: PublishingJob, action: 'retry' | 'cancel') {
    await this.publishing.jobAction(item.id, action);
    await this.load();
  }
}
