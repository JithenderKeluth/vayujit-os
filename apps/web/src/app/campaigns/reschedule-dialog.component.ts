import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  Output,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import type {
  CampaignActivity,
  CampaignRescheduleConfirmationResult,
  CampaignReschedulePreviewResponse,
  CampaignRescheduleHistoryItem,
} from '@vayujit/shared';
import { CampaignService } from './campaign.service';

@Component({
  selector: 'app-reschedule-dialog',
  imports: [DatePipe, ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="reschedule-panel" aria-labelledby="reschedule-title">
      <header>
        <h3 id="reschedule-title">Reschedule Activity</h3>
        <p>Preview the change before confirming it. The server remains authoritative.</p>
      </header>
      <form [formGroup]="form" (ngSubmit)="preview()" novalidate>
        <label>Local date <input type="date" formControlName="date" required /></label>
        <label>Local time <input type="time" formControlName="time" required /></label>
        <label
          >IANA timezone
          <input formControlName="timezone" list="iana-timezones" required aria-describedby="timezone-help" />
        </label>
        <datalist id="iana-timezones">
          <option value="UTC"></option><option value="America/New_York"></option>
          <option value="Europe/London"></option><option value="Asia/Kolkata"></option>
        </datalist>
        <p id="timezone-help">Use an IANA timezone such as America/New_York.</p>
        <label>Reason <textarea formControlName="reason" maxlength="500" rows="3"></textarea></label>
        @if (error()) {
          <p #errorRegion class="op-error" role="alert" tabindex="-1">{{ error() }}</p>
        }
        <button type="submit" [disabled]="pending() || form.invalid">Preview change</button>
      </form>

      @if (previewResult(); as value) {
        <article class="reschedule-preview" aria-live="polite">
          <h4>Review impact</h4>
          <dl>
            <dt>Original local</dt><dd>{{ activity.scheduled_local_date }} {{ activity.scheduled_local_time }} ({{ activity.timezone_name }})</dd>
            <dt>Original UTC</dt><dd>{{ value.original_scheduled_at_utc | date: 'medium' : 'UTC' }}</dd>
            <dt>Proposed local</dt><dd>{{ value.proposed_local_datetime }} ({{ value.timezone }})</dd>
            <dt>Proposed UTC</dt><dd>{{ value.proposed_scheduled_at_utc | date: 'medium' : 'UTC' }}</dd>
            <dt>UTC offset</dt><dd>{{ value.utc_offset || 'Not resolved' }}</dd>
            <dt>DST classification</dt><dd>{{ value.dst_classification }}</dd>
            <dt>Current schedule/job</dt><dd>{{ value.current_schedule_status || 'None' }} / {{ value.current_job_status || 'None' }}</dd>
          </dl>
          @if (value.dst_classification === 'ambiguous_local_time') {
            <label
              >Choose DST interpretation
              <select [value]="selectedFold()" (change)="selectFold($event)" aria-describedby="fold-help">
                <option value="">Choose a fold</option>
                <option value="0">Fold 0 · first occurrence · refresh preview</option>
                <option value="1">Fold 1 · second occurrence · refresh preview</option>
              </select>
            </label>
            <p id="fold-help">Both interpretations are shown by the refreshed preview; no fold is guessed.</p>
          }
          @if (value.dst_classification === 'nonexistent_local_time') {
            <p class="op-error">This local time does not exist because of a daylight-saving transition. Choose another time.</p>
          }
          @for (warning of value.warnings; track warning) { <p class="warning">{{ warning }}</p> }
          @for (issue of value.readiness_issues; track issue.code + issue.activity_id) {
            <p class="warning">{{ issue.code }}: {{ issue.safe_message }}</p>
          }
          @for (conflict of value.conflicts; track conflict.conflict_type + conflict.activity_ids.join()) {
            <p class="warning">{{ conflict.conflict_type }}: {{ conflict.safe_explanation }}</p>
          }
          <p>{{ value.safe_message }}</p>
          <div class="reschedule-actions">
            <button type="button" (click)="confirm()" [disabled]="pending() || !value.confirmation_required || value.dst_classification === 'ambiguous_local_time' && selectedFold() === null">
              {{ pending() ? 'Confirming…' : 'Confirm reschedule' }}
            </button>
            <button type="button" class="secondary" (click)="preview()" [disabled]="pending()">Refresh preview</button>
          </div>
        </article>
      }

      @if (history().length) {
        <section aria-labelledby="reschedule-history-title">
          <h4 id="reschedule-history-title">Reschedule history</h4>
          <ol>
            @for (item of history(); track item.id) {
              <li>
                <strong>{{ item.status }}</strong> · {{ item.requested_local_datetime }} ({{ item.requested_timezone }})
                <span>{{ item.reason }}</span>
                @if (item.original_schedule_id) { <a [routerLink]="'/publishing/schedules/' + item.original_schedule_id">Original schedule</a> }
                @if (item.replacement_schedule_id) { <a [routerLink]="'/publishing/schedules/' + item.replacement_schedule_id">Replacement schedule</a> }
                @if (item.original_job_id) { <a [routerLink]="'/publishing/jobs/' + item.original_job_id">Original job</a> }
                @if (item.replacement_job_id) { <a [routerLink]="'/publishing/jobs/' + item.replacement_job_id">Replacement job</a> }
              </li>
            }
          </ol>
        </section>
      }
      @if (confirmationResult(); as result) {
        <section class="reschedule-success" aria-live="polite">
          <h4>Reschedule confirmed</h4>
          <p>{{ result.safe_message }}</p>
          @if (target(result, 'activity'); as link) { <a [routerLink]="link">View Activity</a> }
          @if (target(result, 'replacement_schedule'); as link) { <a [routerLink]="link">View replacement schedule</a> }
          @if (target(result, 'replacement_job'); as link) { <a [routerLink]="link">View replacement job</a> }
          @if (target(result, 'original_schedule'); as link) { <a [routerLink]="link">View original schedule history</a> }
          @if (target(result, 'original_job'); as link) { <a [routerLink]="link">View original job history</a> }
          <p class="op-muted">Correlation: {{ result.correlation_id }}</p>
          <button type="button" class="secondary" (click)="completed.emit()">Close</button>
        </section>
      }
    </section>
  `,
  styleUrl: './campaigns.css',
})
export class RescheduleDialogComponent {
  @Input({ required: true }) campaignId!: string;
  @Input({ required: true }) activity!: CampaignActivity;
  @Output() completed = new EventEmitter<void>();
  @ViewChild('errorRegion') private errorRegion?: ElementRef<HTMLElement>;
  private readonly api = inject(CampaignService);
  private readonly fb = inject(FormBuilder);
  readonly pending = signal(false);
  readonly error = signal('');
  readonly previewResult = signal<CampaignReschedulePreviewResponse | null>(null);
  readonly confirmationResult = signal<CampaignRescheduleConfirmationResult | null>(null);
  readonly history = signal<CampaignRescheduleHistoryItem[]>([]);
  readonly selectedFold = signal<0 | 1 | null>(null);
  readonly form = this.fb.nonNullable.group({
    date: ['', Validators.required],
    time: ['', Validators.required],
    timezone: ['UTC', [Validators.required, Validators.maxLength(100)]],
    reason: ['', Validators.maxLength(500)],
  });
  private fingerprint = '';

  ngOnInit(): void {
    void this.loadHistory();
    const local = this.activity.scheduled_local_date;
    this.form.patchValue({ date: local, time: this.activity.scheduled_local_time.slice(0, 5), timezone: this.activity.timezone_name });
  }

  async preview(): Promise<void> {
    this.error.set('');
    this.previewResult.set(null);
    this.confirmationResult.set(null);
    this.fingerprint = '';
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    const value = this.form.getRawValue();
    this.pending.set(true);
    try {
      const result = await this.api.previewActivityReschedule(this.campaignId, {
        activity_id: this.activity.id,
        proposed_local_datetime: `${value.date}T${value.time}:00`,
        proposed_timezone: value.timezone,
        reason: value.reason,
        expected_activity_row_version: this.activity.row_version,
        fold: this.selectedFold(),
      });
      this.previewResult.set(result);
      this.fingerprint = result.preview_fingerprint;
    } catch (error) {
      this.showError(this.safeError(error, 'Unable to preview this reschedule.'));
    } finally { this.pending.set(false); }
  }

  selectFold(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.selectedFold.set(value === '' ? null : (Number(value) as 0 | 1));
    if (value !== '') void this.preview();
  }

  async confirm(): Promise<void> {
    const value = this.previewResult();
    if (!value || !this.fingerprint || !value.confirmation_required || this.pending()) return;
    this.pending.set(true);
    this.error.set('');
    try {
      const response = await this.api.confirmActivityReschedule({
        action: 'reschedule_activity',
        campaign_id: this.campaignId,
        activity_id: this.activity.id,
        expected_activity_row_version: this.activity.row_version,
        proposed_local_datetime: value.proposed_local_datetime,
        proposed_timezone: value.timezone,
        reason: this.form.controls.reason.value,
        preview_fingerprint: this.fingerprint,
        confirm: true,
        ...(value.fold === null ? {} : { fold: value.fold }),
      });
      this.confirmationResult.set(response.result);
      this.fingerprint = '';
      await this.loadHistory();
    } catch (error) {
      this.fingerprint = '';
      this.showError(this.safeError(error, 'The reschedule could not be confirmed. Refresh the preview and try again.'));
    } finally { this.pending.set(false); }
  }

  private async loadHistory(): Promise<void> {
    try { this.history.set(await this.api.getActivityRescheduleHistory(this.campaignId, this.activity.id)); } catch { this.history.set([]); }
  }

  private safeError(error: unknown, fallback: string): string {
    if (error instanceof HttpErrorResponse && typeof error.error?.detail === 'string') {
      return error.error.detail;
    }
    if (typeof error === 'object' && error !== null) {
      const detail = (error as { error?: unknown }).error;
      if (
        typeof detail === 'object' &&
        detail !== null &&
        typeof (detail as { detail?: unknown }).detail === 'string'
      ) {
        return (detail as { detail: string }).detail;
      }
    }
    return fallback;
  }

  private showError(message: string): void {
    this.error.set(message);
    setTimeout(() => this.errorRegion?.nativeElement.focus(), 0);
  }

  target(result: CampaignRescheduleConfirmationResult, key: string): string | null {
    return result.navigation_targets[key] || null;
  }
}
