import { TestBed } from '@angular/core/testing';
import type { CampaignActivity } from '@vayujit/shared';
import { vi } from 'vitest';
import { CampaignService } from './campaign.service';
import { RescheduleDialogComponent } from './reschedule-dialog.component';

describe('R5 reschedule-only focus styling', () => {
  function setup() {
    const api = {
      getActivityRescheduleHistory: vi.fn().mockResolvedValue([]),
      previewActivityReschedule: vi.fn(),
      confirmActivityReschedule: vi.fn(),
    };
    TestBed.configureTestingModule({
      imports: [RescheduleDialogComponent],
      providers: [{ provide: CampaignService, useValue: api }],
    });
    const fixture = TestBed.createComponent(RescheduleDialogComponent);
    fixture.componentInstance.campaignId = 'r5-synthetic-campaign';
    fixture.componentInstance.activity = {
      id: 'r5-synthetic-activity',
      campaign_id: 'r5-synthetic-campaign',
      scheduled_local_date: '2026-11-02',
      scheduled_local_time: '09:00:00',
      timezone_name: 'Asia/Kolkata',
      row_version: 1,
    } as CampaignActivity;
    fixture.detectChanges();
    return { fixture, api, root: fixture.nativeElement as HTMLElement };
  }

  it('scopes the existing strong focus token to the reschedule panel', () => {
    const { root } = setup();
    const panel = root.querySelector<HTMLElement>('.reschedule-panel')!;
    expect(getComputedStyle(panel).getPropertyValue('--vj-focus').trim()).toBe(
      'var(--vj-color-brand-strong)',
    );
    expect(document.documentElement.style.getPropertyValue('--vj-focus')).toBe('');
  });

  it('preserves labelled fields and the inline non-modal contract', () => {
    const { root } = setup();
    const panel = root.querySelector<HTMLElement>('.reschedule-panel')!;
    expect(panel.getAttribute('aria-labelledby')).toBe('reschedule-title');
    expect(panel.getAttribute('role')).not.toBe('dialog');
    expect(panel.hasAttribute('aria-modal')).toBe(false);
    expect(root.querySelectorAll('form label').length).toBe(4);
    expect(root.querySelector<HTMLTextAreaElement>('textarea')?.maxLength).toBe(500);
    expect(root.querySelector('[formControlName=timezone]')?.getAttribute('aria-describedby')).toBe(
      'timezone-help',
    );
  });

  it('does not weaken invalid-preview or confirmation prerequisites', async () => {
    const { fixture, api } = setup();
    fixture.componentInstance.form.controls.date.setValue('');
    await fixture.componentInstance.preview();
    await fixture.componentInstance.confirm();
    expect(api.previewActivityReschedule).not.toHaveBeenCalled();
    expect(api.confirmActivityReschedule).not.toHaveBeenCalled();
    expect(fixture.componentInstance.form.touched).toBe(true);
    expect(fixture.componentInstance.previewResult()).toBeNull();
  });
});
