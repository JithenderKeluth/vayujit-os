import { TestBed } from '@angular/core/testing';
import type { CampaignActivity } from '@vayujit/shared';
import { CampaignService } from './campaign.service';
import { RescheduleDialogComponent } from './reschedule-dialog.component';

const activity: CampaignActivity = {
  id: 'activity-1',
  campaign_id: 'campaign-1',
  product_id: null,
  artifact_id: null,
  artifact_version: null,
  destination_id: null,
  connector_key: null,
  requested_action: null,
  activity_type: 'wordpress_create_draft',
  name: 'Activity',
  description: '',
  sequence: 1,
  scheduled_local_date: '2026-10-01',
  scheduled_local_time: '09:00:00',
  timezone_name: 'UTC',
  scheduled_at_utc: '2026-10-01T09:00:00Z',
  duration_minutes: null,
  status: 'missed',
  readiness_status: 'ready',
  schedule_id: null,
  job_id: null,
  publishing_execution_id: null,
  required: true,
  enabled: true,
  failure_code: null,
  safe_failure_message: null,
  correlation_id: null,
  row_version: 4,
};

describe('RescheduleDialogComponent', () => {
  const preview = {
    campaign_id: 'campaign-1',
    activity_id: 'activity-1',
    original_scheduled_at_utc: activity.scheduled_at_utc,
    proposed_local_datetime: '2026-11-01T01:30:00',
    proposed_scheduled_at_utc: '2026-11-01T06:30:00Z',
    timezone: 'America/New_York',
    confirmation_required: true,
    preview_fingerprint: 'fp-1',
    safe_message: 'Review',
    correlation_id: 'corr-1',
    dst_classification: 'ambiguous_local_time' as const,
    utc_offset: '-05:00',
    fold: 1 as const,
    issue_code: null,
    warnings: [],
    readiness_issues: [],
    conflicts: [],
    current_schedule_status: 'active',
    current_job_status: 'pending',
  };

  it('keeps confirmation disabled until a normal preview is returned', async () => {
    const api = {
      previewActivityReschedule: () =>
        Promise.resolve({ ...preview, dst_classification: 'normal' as const, fold: null }),
      confirmActivityReschedule: () =>
        Promise.resolve({ action: 'reschedule_activity', result: { outcome: 'succeeded' } }),
      getActivityRescheduleHistory: () => Promise.resolve([]),
    };
    await TestBed.configureTestingModule({
      imports: [RescheduleDialogComponent],
      providers: [{ provide: CampaignService, useValue: api }],
    }).compileComponents();
    const fixture = TestBed.createComponent(RescheduleDialogComponent);
    fixture.componentInstance.campaignId = 'campaign-1';
    fixture.componentInstance.activity = activity;
    fixture.detectChanges();
    await fixture.componentInstance.preview();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('normal');
    expect(fixture.nativeElement.querySelector('button[type=submit]')).toBeTruthy();
  });

  it('renders the DST fold selector and refreshes when the fold changes', async () => {
    let calls = 0;
    const api = {
      previewActivityReschedule: () => {
        calls += 1;
        return Promise.resolve(preview);
      },
      confirmActivityReschedule: () => Promise.reject(new Error('not expected')),
      getActivityRescheduleHistory: () => Promise.resolve([]),
    };
    await TestBed.configureTestingModule({
      imports: [RescheduleDialogComponent],
      providers: [{ provide: CampaignService, useValue: api }],
    }).compileComponents();
    const fixture = TestBed.createComponent(RescheduleDialogComponent);
    fixture.componentInstance.campaignId = 'campaign-1';
    fixture.componentInstance.activity = activity;
    fixture.detectChanges();
    await fixture.componentInstance.preview();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Choose DST interpretation');
    fixture.componentInstance.selectFold({ target: { value: '0' } } as unknown as Event);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(calls).toBe(2);
  });

  it('clears the fingerprint after a stale confirmation error', async () => {
    const api = {
      previewActivityReschedule: () =>
        Promise.resolve({ ...preview, dst_classification: 'normal' as const, fold: null }),
      confirmActivityReschedule: () =>
        Promise.reject(new Error('The reschedule preview is stale or invalid.')),
      getActivityRescheduleHistory: () => Promise.resolve([]),
    };
    await TestBed.configureTestingModule({
      imports: [RescheduleDialogComponent],
      providers: [{ provide: CampaignService, useValue: api }],
    }).compileComponents();
    const fixture = TestBed.createComponent(RescheduleDialogComponent);
    fixture.componentInstance.campaignId = 'campaign-1';
    fixture.componentInstance.activity = activity;
    fixture.detectChanges();
    await fixture.componentInstance.preview();
    await fixture.componentInstance.confirm();
    expect(fixture.componentInstance.error()).toContain('stale');
  });
});
