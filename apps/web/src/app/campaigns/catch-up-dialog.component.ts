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
  CampaignCatchUpPreviewResponse,
  CampaignRescheduleConfirmationResult,
} from '@vayujit/shared';
import { CampaignService } from './campaign.service';

@Component({
  selector: 'app-catch-up-dialog',
  imports: [DatePipe, ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="reschedule-panel" aria-labelledby="catch-up-title">
      <header>
        <h3 id="catch-up-title">Create one catch-up Activity</h3>
        <p>The missed Activity stays unchanged. Review the additive catch-up before confirming.</p>
      </header>
      <form [formGroup]="form" (ngSubmit)="preview()" novalidate>
        <label>Catch-up date <input type="date" formControlName="date" required /></label>
        <label>Catch-up time <input type="time" formControlName="time" required /></label>
        <label>IANA timezone <input formControlName="timezone" required aria-describedby="catch-up-timezone-help" /></label>
        <p id="catch-up-timezone-help">Use an IANA timezone such as America/New_York.</p>
        <label>Reason <textarea formControlName="reason" maxlength="500" rows="3"></textarea></label>
        @if (error()) { <p #errorRegion class="op-error" role="alert" tabindex="-1">{{ error() }}</p> }
        <button type="submit" [disabled]="pending() || form.invalid">Preview catch-up</button>
      </form>
      @if (previewResult(); as value) {
        <article class="reschedule-preview" aria-live="polite">
          <h4>Review catch-up impact</h4>
          <p><strong>Original missed Activity:</strong> {{ value.original_activity_name }}</p>
          <p><strong>Artifact:</strong> {{ value.artifact_version ? ('Version ' + value.artifact_version) : 'Unavailable' }} ({{ value.artifact_status || 'unknown' }})</p>
          <p><strong>Destination:</strong> {{ value.destination_status || 'Unavailable' }}</p>
          <dl>
            <dt>Original UTC</dt><dd>{{ value.original_scheduled_at_utc | date: 'medium' : 'UTC' }}</dd>
            <dt>Catch-up local</dt><dd>{{ value.proposed_local_datetime }} ({{ value.timezone }})</dd>
            <dt>Catch-up UTC</dt><dd>{{ value.proposed_scheduled_at_utc | date: 'medium' : 'UTC' }}</dd>
            <dt>UTC offset</dt><dd>{{ value.utc_offset || 'Not resolved' }}</dd>
            <dt>DST classification</dt><dd>{{ value.dst_classification }}</dd>
          </dl>
          @if (value.dst_classification === 'ambiguous_local_time') {
            <label>Choose DST interpretation
              <select [value]="selectedFold()" (change)="selectFold($event)">
                <option value="">Choose a fold</option>
                <option value="0">Fold 0 - first occurrence</option>
                <option value="1">Fold 1 - second occurrence</option>
              </select>
            </label>
          }
          @if (value.dst_classification === 'nonexistent_local_time') {
            <p class="op-error">This local time does not exist because of a daylight-saving transition. Choose another time.</p>
          }
          @for (warning of value.warnings; track warning) { <p class="warning">{{ warning }}</p> }
          @for (warning of value.dependency_warnings; track warning) { <p class="warning">Dependency: {{ warning }}</p> }
          @for (issue of value.readiness_issues; track issue.code + issue.activity_id) { <p class="warning">{{ issue.code }}: {{ issue.safe_message }}</p> }
          <p>{{ value.safe_message }}</p>
          <div class="reschedule-actions">
            <button type="button" (click)="confirm()" [disabled]="pending() || !value.confirmation_required || (value.dst_classification === 'ambiguous_local_time' && selectedFold() === null)">{{ pending() ? 'Confirming...' : 'Confirm catch-up' }}</button>
            <button type="button" class="secondary" (click)="preview()" [disabled]="pending()">Refresh preview</button>
          </div>
        </article>
      }
      @if (result(); as value) {
        <section class="reschedule-success" aria-live="polite">
          <h4>Catch-up created</h4>
          <p>{{ value.safe_message }}</p>
          @if (value.navigation_targets['activity']) { <a [routerLink]="value.navigation_targets['activity']">View catch-up Activity</a> }
          @if (value.navigation_targets['schedule']) { <a [routerLink]="value.navigation_targets['schedule']">View schedule</a> }
          @if (value.navigation_targets['job']) { <a [routerLink]="value.navigation_targets['job']">View job</a> }
          <p class="op-muted">Correlation: {{ value.correlation_id }}</p>
          <button type="button" class="secondary" (click)="completed.emit()">Close</button>
        </section>
      }
    </section>
  `,
  styleUrl: './campaigns.css',
})
export class CatchUpDialogComponent {
  @Input({ required: true }) campaignId!: string;
  @Input({ required: true }) activity!: CampaignActivity;
  @Output() completed = new EventEmitter<void>();
  @ViewChild('errorRegion') private errorRegion?: ElementRef<HTMLElement>;
  private readonly api = inject(CampaignService);
  private readonly fb = inject(FormBuilder);
  readonly pending = signal(false);
  readonly error = signal('');
  readonly previewResult = signal<CampaignCatchUpPreviewResponse | null>(null);
  readonly result = signal<CampaignRescheduleConfirmationResult | null>(null);
  readonly selectedFold = signal<0 | 1 | null>(null);
  readonly form = this.fb.nonNullable.group({
    date: ['', Validators.required],
    time: ['', Validators.required],
    timezone: ['UTC', [Validators.required, Validators.maxLength(100)]],
    reason: ['', Validators.maxLength(500)],
  });
  private fingerprint = '';

  ngOnInit(): void {
    this.form.patchValue({
      date: this.activity.scheduled_local_date,
      time: this.activity.scheduled_local_time.slice(0, 5),
      timezone: this.activity.timezone_name,
    });
  }

  async preview(): Promise<void> {
    this.error.set('');
    this.previewResult.set(null);
    this.result.set(null);
    this.fingerprint = '';
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    this.pending.set(true);
    try {
      const response = await this.api.previewCreateCatchUp(this.campaignId, {
        activity_id: this.activity.id,
        proposed_local_datetime: `${value.date}T${value.time}:00`,
        proposed_timezone: value.timezone,
        reason: value.reason,
        expected_activity_row_version: this.activity.row_version,
        fold: this.selectedFold(),
      });
      this.previewResult.set(response);
      this.fingerprint = response.preview_fingerprint;
    } catch (error) {
      this.showError(this.safeError(error, 'Unable to preview this catch-up.'));
    } finally {
      this.pending.set(false);
    }
  }

  selectFold(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.selectedFold.set(value === '' ? null : (Number(value) as 0 | 1));
    if (value !== '') void this.preview();
  }

  async confirm(): Promise<void> {
    const preview = this.previewResult();
    if (!preview || !this.fingerprint || !preview.confirmation_required || this.pending()) return;
    this.pending.set(true);
    try {
      const response = await this.api.confirmActivityReschedule({
        action: 'create_one_catch_up',
        campaign_id: this.campaignId,
        activity_id: this.activity.id,
        expected_activity_row_version: this.activity.row_version,
        proposed_local_datetime: preview.proposed_local_datetime,
        proposed_timezone: preview.timezone,
        reason: this.form.controls.reason.value,
        preview_fingerprint: this.fingerprint,
        confirm: true,
        ...(preview.fold === null ? {} : { fold: preview.fold }),
      });
      this.fingerprint = '';
      this.result.set(response.result);
    } catch (error) {
      this.fingerprint = '';
      this.showError(this.safeError(error, 'The catch-up could not be created. Refresh the preview and try again.'));
    } finally {
      this.pending.set(false);
    }
  }

  private showError(message: string): void {
    this.error.set(message);
    setTimeout(() => this.errorRegion?.nativeElement.focus(), 0);
  }

  private safeError(error: unknown, fallback: string): string {
    if (error instanceof HttpErrorResponse && typeof error.error?.detail === 'string') return error.error.detail;
    if (typeof error === 'object' && error !== null) {
      const detail = (error as { error?: unknown }).error;
      if (typeof detail === 'object' && detail !== null && typeof (detail as { detail?: unknown }).detail === 'string') {
        return (detail as { detail: string }).detail;
      }
    }
    return fallback;
  }
}
