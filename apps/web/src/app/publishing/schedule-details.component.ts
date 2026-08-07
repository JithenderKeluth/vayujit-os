import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type { PublishingSchedule } from '@vayujit/shared';
import { PublishingService } from './publishing.service';

@Component({
  selector: 'app-schedule-details',
  imports: [DatePipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<section class="op-page">
    <header>
      <p class="op-eyebrow">Publishing schedule</p>
      <h1>{{ schedule()?.name || 'Schedule' }}</h1>
    </header>
    @if (schedule(); as value) {
      <article class="op-card">
        <p>{{ value.schedule_type }} · {{ value.connector_key }} · {{ value.requested_action }}</p>
        <p>Local {{ value.local_scheduled_at | date: 'medium' }} {{ value.timezone_name }}</p>
        <p>UTC {{ value.scheduled_at_utc | date: 'medium' : 'UTC' }}</p>
        <p>
          Next {{ value.next_run_at_utc | date: 'medium' }} · Occurrences
          {{ value.materialized_occurrence_count }} / {{ value.max_occurrences }}
        </p>
        @if (value.archived) {
          <p class="op-error">Superseded by an Activity reschedule.</p>
          <p>Original schedule history is preserved.</p>
        }
        <p>Missed policy {{ value.missed_occurrence_policy }}</p>
        <a [routerLink]="['/publishing/jobs']" [queryParams]="{ schedule_id: value.id }"
          >View jobs</a
        >
      </article>
    }
  </section>`,
})
export class ScheduleDetailsComponent implements OnInit {
  private readonly api = inject(PublishingService);
  private readonly route = inject(ActivatedRoute);
  readonly schedule = signal<PublishingSchedule | null>(null);
  ngOnInit(): void {
    void this.load();
  }

  private async load(): Promise<void> {
    this.schedule.set(await this.api.schedule(this.route.snapshot.paramMap.get('id')!));
  }
}
