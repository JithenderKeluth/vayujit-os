import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type { PublishingJob, PublishingJobAttempt } from '@vayujit/shared';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-job-details',
  imports: [DatePipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section class="op-page">
    <header>
      <p class="op-eyebrow">Publishing job</p>
      <h1>Execution timeline</h1>
    </header>
    @if (job(); as value) {
      <article class="op-card">
        <p><strong>State:</strong> {{ value.state }}</p>
        @if (value.recovery_state === 'superseded') {
          <p class="op-error">Superseded by Activity rescheduling.</p>
          <p>
            {{ value.recovery_reason || 'This job is retained for history and is not retryable.' }}
          </p>
        }
        <p><strong>Correlation:</strong> {{ value.correlation_id || 'Not recorded' }}</p>
        <p>
          <strong>Lease:</strong> {{ value.lease_owner || 'None' }}
          @if (value.lease_expires_at) {
            until {{ value.lease_expires_at | date: 'medium' }}
          }
        </p>
        <nav>
          <a [routerLink]="['/publishing/schedules', value.schedule_id]">Schedule</a> ·
          <a [routerLink]="['/products', value.product_id]">Product</a> ·
          <a [routerLink]="['/ai/artifacts', value.artifact_id]"
            >Artifact v{{ value.artifact_version }}</a
          >
          @if (value.publishing_execution_id) {
            ·
            <a [routerLink]="['/publishing/executions', value.publishing_execution_id]"
              >Publishing execution</a
            >
          }
        </nav>
        @if (value.last_error_message) {
          <p class="op-error">{{ value.last_error_message }}</p>
        }
      </article>
    }
    <ol class="op-card" aria-label="Job attempt timeline">
      @for (item of attempts(); track item.id) {
        <li>
          <h2>Attempt {{ item.attempt_number }} · {{ item.outcome }}</h2>
          <p>
            Worker {{ item.worker_id }} · {{ item.started_at | date: 'medium' }} →
            {{ item.completed_at | date: 'medium' }}
          </p>
          <p>
            Retryable {{ item.retryable ? 'Yes' : 'No' }}
            @if (item.delay_seconds) {
              · Retry delay {{ item.delay_seconds }} seconds
            }
          </p>
          <p>Correlation {{ item.correlation_id || 'Not recorded' }}</p>
          @if (item.safe_error_message) {
            <p class="op-error">{{ item.safe_error_message }}</p>
          }
        </li>
      } @empty {
        <li>No attempts have started.</li>
      }
    </ol>
  </section>`,
})
export class JobDetailsComponent implements OnInit {
  private readonly api = inject(PublishingService);
  private readonly route = inject(ActivatedRoute);
  readonly job = signal<PublishingJob | null>(null);
  readonly attempts = signal<PublishingJobAttempt[]>([]);
  ngOnInit(): void {
    void this.load();
  }

  private async load(): Promise<void> {
    const id = this.route.snapshot.paramMap.get('id')!;
    const [job, attempts] = await Promise.all([this.api.job(id), this.api.jobAttempts(id)]);
    this.job.set(job);
    this.attempts.set(attempts);
  }
}
