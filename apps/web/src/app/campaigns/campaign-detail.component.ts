import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import type {
  Campaign,
  CampaignActivity,
  CampaignConflict,
  CampaignProgress,
  CampaignReadiness,
  CampaignRecoveryProjection,
} from '@vayujit/shared';
import { CampaignService } from './campaign.service';
import { CatchUpDialogComponent } from './catch-up-dialog.component';
import { RescheduleDialogComponent } from './reschedule-dialog.component';

@Component({
  selector: 'app-campaign-detail',
  imports: [DatePipe, FormsModule, RouterLink, RescheduleDialogComponent, CatchUpDialogComponent],
  template: `
    <section class="page">
      @if (campaign(); as value) {
        <header class="page-header">
          <div>
            <p class="eyebrow">Campaign</p>
            <h1>{{ value.name }}</h1>
            <span class="badge">{{ value.status }}</span>
          </div>
          <div class="actions">
            <a class="button" [routerLink]="['/campaigns', value.id, 'activities', 'new']"
              >Add activity</a
            >
            <a class="button" [routerLink]="['/calendar']" [queryParams]="{ campaign: value.id }"
              >Calendar</a
            >
            <a class="button" [routerLink]="['/campaigns', value.id, 'dependencies']"
              >Dependencies</a
            >
          </div>
        </header>
        <div class="grid">
          <section class="panel">
            <h2>Window</h2>
            <p>
              {{ value.start_at_utc | date: 'medium' }} – {{ value.end_at_utc | date: 'medium' }}
            </p>
            <p>{{ value.timezone_name }}</p>
          </section>
          @if (progress(); as state) {
            <section class="panel">
              <h2>Progress</h2>
              <progress [value]="state.completion_percentage" max="100">
                {{ state.completion_percentage }}%
              </progress>
              <p>
                {{ state.succeeded }} succeeded · {{ state.failed }} failed ·
                {{ state.blocked }} blocked
              </p>
            </section>
          }
        </div>
        <div class="actions">
          <button (click)="validate()">Review readiness</button>
          <button (click)="release()" [disabled]="!['draft', 'planning'].includes(value.status)">
            Release
          </button>
          <button (click)="schedule()" [disabled]="value.status !== 'ready'">
            Schedule all ready
          </button>
          <button
            (click)="pause()"
            [disabled]="!['ready', 'scheduled', 'running'].includes(value.status)"
          >
            Pause
          </button>
          @if (value.status === 'paused') {
            <label
              >Missed activities<select [(ngModel)]="resumePolicy">
                <option value="skip_missed">Skip missed</option>
                <option value="run_next">Run next</option>
                <option value="one_catch_up">One catch-up</option>
                <option value="reschedule_manually">Reschedule manually</option>
              </select></label
            ><button (click)="resume()">Resume</button>
          }
          <button
            class="danger"
            (click)="cancel()"
            [disabled]="['completed', 'cancelled', 'archived'].includes(value.status)"
          >
            Cancel
          </button>
        </div>
        @if (message()) {
          <p aria-live="polite">{{ message() }}</p>
        }
        @if (readiness(); as check) {
          <section class="panel">
            <h2>Readiness: {{ check.state }}</h2>
            @if (!check.issues.length) {
              <p>All checks passed.</p>
            }
            @for (issue of check.issues; track issue.code + issue.activity_id) {
              <article [class]="issue.severity">
                <strong>{{ issue.code }}</strong>
                <p>{{ issue.safe_message }}</p>
                <small>{{ issue.suggested_resolution }}</small>
              </article>
            }
          </section>
        }
        @if (conflicts().length) {
          <section class="panel">
            <h2>Conflicts</h2>
            @for (
              conflict of conflicts();
              track conflict.conflict_type + conflict.activity_ids.join()
            ) {
              <article class="conflict">
                <strong>{{ conflict.conflict_type }}</strong>
                <p>{{ conflict.safe_explanation }}</p>
                <small>{{ conflict.suggested_correction }}</small>
              </article>
            }
          </section>
        }
        <section>
          <h2>Activities</h2>
          @if (!activities().length) {
            <p>No activities yet.</p>
          }
          <div class="grid">
            @for (activity of activities(); track activity.id) {
              <article class="card">
                <span class="badge">{{ activity.status }}</span>
                <h3>{{ activity.name }}</h3>
                <p>{{ activity.activity_type }}</p>
                <p>
                  {{ activity.scheduled_at_utc | date: 'medium' }} · {{ activity.timezone_name }}
                </p>
                <p>Readiness: {{ activity.readiness_status }}</p>
                @if (activity.replaces_activity_id) {
                  <p class="op-muted">
                    Catch-up Activity for missed original {{ activity.replaces_activity_id }}
                  </p>
                }
                @if (activity.replaced_by_activity_id) {
                  <p class="op-muted">
                    Original Activity replaced by {{ activity.replaced_by_activity_id }}
                  </p>
                }
                @if (activity.replacement_reason) {
                  <p class="op-muted">Reason: {{ activity.replacement_reason }}</p>
                }
                @if (rescheduleAction(activity); as action) {
                  @if (action.eligible_actions.includes('reschedule_activity')) {
                    <button type="button" (click)="reschedulingActivityId.set(activity.id)">
                      Reschedule Activity
                    </button>
                  } @else if (action.safe_failure_message) {
                    <p class="op-muted">
                      Rescheduling unavailable: {{ action.safe_failure_message }}
                    </p>
                  }
                  @if (action.eligible_actions.includes('create_one_catch_up')) {
                    <button type="button" (click)="catchingUpActivityId.set(activity.id)">
                      Create one catch-up
                    </button>
                  }
                }
                @if (reschedulingActivityId() === activity.id) {
                  <app-reschedule-dialog
                    [campaignId]="value.id"
                    [activity]="activity"
                    (completed)="closeReschedule()"
                  />
                }
                @if (catchingUpActivityId() === activity.id) {
                  <app-catch-up-dialog
                    [campaignId]="value.id"
                    [activity]="activity"
                    (completed)="closeCatchUp()"
                  />
                }
                @if (activity.job_id) {
                  <a [routerLink]="['/publishing/jobs', activity.job_id]">Open job</a>
                }
                @if (activity.publishing_execution_id) {
                  <a [routerLink]="['/publishing/executions', activity.publishing_execution_id]"
                    >Open execution</a
                  >
                }
              </article>
            }
          </div>
        </section>
      } @else {
        <p>Loading Campaign…</p>
      }
    </section>
  `,
  styleUrl: './campaigns.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CampaignDetailComponent {
  private readonly api = inject(CampaignService);
  private readonly id = inject(ActivatedRoute).snapshot.paramMap.get('id')!;
  readonly campaign = signal<Campaign | null>(null);
  readonly activities = signal<CampaignActivity[]>([]);
  readonly readiness = signal<CampaignReadiness | null>(null);
  readonly conflicts = signal<CampaignConflict[]>([]);
  readonly progress = signal<CampaignProgress | null>(null);
  readonly recovery = signal<CampaignRecoveryProjection[]>([]);
  readonly reschedulingActivityId = signal<string | null>(null);
  readonly catchingUpActivityId = signal<string | null>(null);
  readonly message = signal('');
  resumePolicy = 'skip_missed';
  constructor() {
    void this.load();
  }
  private async load(): Promise<void> {
    const [campaign, activities, conflicts, progress] = await Promise.all([
      this.api.get(this.id),
      this.api.activities(this.id),
      this.api.conflicts(this.id),
      this.api.progress(this.id),
    ]);
    this.campaign.set(campaign);
    this.activities.set(activities);
    this.conflicts.set(conflicts);
    this.progress.set(progress);
    try {
      const recovery = await this.api.recovery();
      this.recovery.set(recovery.filter((item) => item.campaign_id === this.id));
    } catch {
      this.recovery.set([]);
    }
  }
  async validate(): Promise<void> {
    this.readiness.set(await this.api.readiness(this.id));
    await this.load();
  }
  async release(): Promise<void> {
    this.campaign.set(await this.api.release(this.id));
  }
  async schedule(): Promise<void> {
    await this.api.schedule(this.id);
    this.message.set('Campaign activities scheduled.');
    await this.load();
  }
  async pause(): Promise<void> {
    this.campaign.set(await this.api.pause(this.id));
  }
  async resume(): Promise<void> {
    this.campaign.set(await this.api.resume(this.id, this.resumePolicy));
  }
  async cancel(): Promise<void> {
    const reason = globalThis.prompt('Cancellation reason');
    if (reason) this.campaign.set(await this.api.cancel(this.id, reason));
  }
  rescheduleAction(activity: CampaignActivity): CampaignRecoveryProjection | null {
    return this.recovery().find((item) => item.activity_id === activity.id) || null;
  }
  closeReschedule(): void {
    this.reschedulingActivityId.set(null);
    void this.load();
  }
  closeCatchUp(): void {
    this.catchingUpActivityId.set(null);
    void this.load();
  }
}
