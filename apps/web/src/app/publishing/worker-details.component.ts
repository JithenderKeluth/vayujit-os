import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type { PublishingJob, PublishingWorker } from '@vayujit/shared';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-worker-details',
  imports: [DatePipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section class="op-page">
    <header>
      <p class="op-eyebrow">Operations worker</p>
      <h1>{{ worker()?.worker_id || 'Worker' }}</h1>
    </header>
    @if (worker(); as value) {
      <article class="op-card">
        <p>Status {{ value.status }} · version {{ value.version }}</p>
        <p>
          Started {{ value.process_started_at | date: 'medium' }} · heartbeat
          {{ value.last_heartbeat_at | date: 'medium' }}
        </p>
        <p>
          Concurrency {{ value.concurrency }} · active {{ value.active_jobs }} · completed
          {{ value.completed_jobs }} · failed {{ value.failed_jobs }}
        </p>
        <p>
          Lease renewal failures {{ value.lease_renewal_failures }} · stale recoveries
          {{ value.stale_recoveries }}
        </p>
      </article>
    }
    <article class="op-card">
      <h2>Recent leased jobs</h2>
      @for (job of jobs(); track job.id) {
        <p>
          <a [routerLink]="['/publishing/jobs', job.id]"
            >{{ job.requested_action }} · {{ job.state }}</a
          >
        </p>
      } @empty {
        <p>No recent jobs.</p>
      }
    </article>
  </section>`,
})
export class WorkerDetailsComponent implements OnInit {
  private readonly api = inject(PublishingService);
  private readonly route = inject(ActivatedRoute);
  readonly worker = signal<(PublishingWorker & { recent_jobs: PublishingJob[] }) | null>(null);
  readonly jobs = signal<PublishingJob[]>([]);
  ngOnInit(): void {
    void this.load();
  }

  private async load(): Promise<void> {
    const value = await this.api.worker(this.route.snapshot.paramMap.get('id')!);
    this.worker.set(value);
    this.jobs.set(value.recent_jobs);
  }
}
