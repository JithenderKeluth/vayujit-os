import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type { PublishingJob } from '@vayujit/shared';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-publishing-jobs',
  imports: [DatePipe, FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section class="op-page">
    <header>
      <p class="op-eyebrow">Publishing runtime</p>
      <h1>Jobs</h1>
    </header>
    <div class="op-filters">
      <label>State<input [(ngModel)]="state" (ngModelChange)="load()" /></label>
      <label
        >Connector<select [(ngModel)]="connector" (ngModelChange)="load()">
          <option value="">All</option>
          <option value="wordpress">WordPress</option>
          <option value="shopify">Shopify</option>
        </select></label
      >
      <label
        ><input type="checkbox" [(ngModel)]="overdue" (ngModelChange)="load()" /> Overdue</label
      >
      <label
        ><input type="checkbox" [(ngModel)]="retryable" (ngModelChange)="load()" /> Retryable</label
      >
    </div>
    @if (loading()) {
      <p role="status">Loading jobs…</p>
    }
    @if (error()) {
      <p role="alert" class="op-error">{{ error() }}</p>
    }
    <div class="op-card">
      <table>
        <thead>
          <tr>
            <th>Scheduled</th>
            <th>Connector</th>
            <th>Action</th>
            <th>State</th>
            <th>Artifact</th>
            <th>Attempts</th>
            <th>Lease / delay</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (item of jobs(); track item.id) {
            <tr>
              <td>{{ item.scheduled_at_utc | date: 'medium' }}</td>
              <td>{{ item.connector_key }}</td>
              <td>{{ item.requested_action }}</td>
              <td>{{ item.maintenance_blocked_at ? 'maintenance blocked' : item.state }}</td>
              <td>v{{ item.artifact_version }}</td>
              <td>{{ item.execution_attempt_count }} / {{ item.max_execution_attempts }}</td>
              <td>
                @if (item.lease_owner) {
                  {{ item.lease_owner }} until {{ item.lease_expires_at | date: 'medium' }}
                } @else if (item.next_retry_at) {
                  Retry {{ item.next_retry_at | date: 'medium' }}
                } @else {
                  —
                }
              </td>
              <td>
                <a [routerLink]="['/publishing/jobs', item.id]">Timeline</a>
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
              <td colspan="8">No jobs yet.</td>
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
  readonly loading = signal(true);
  readonly error = signal('');
  state = '';
  connector = '';
  overdue = false;
  retryable = false;
  ngOnInit() {
    void this.load();
  }
  async load() {
    this.loading.set(true);
    try {
      this.jobs.set(
        (
          await this.publishing.jobs({
            state: this.state,
            connector_key: this.connector,
            overdue: this.overdue || undefined,
            retryable: this.retryable || undefined,
          })
        ).items,
      );
      this.error.set('');
    } catch {
      this.error.set('Publishing jobs are unavailable.');
    } finally {
      this.loading.set(false);
    }
  }
  async act(item: PublishingJob, action: 'retry' | 'cancel') {
    await this.publishing.jobAction(item.id, action);
    await this.load();
  }
}
