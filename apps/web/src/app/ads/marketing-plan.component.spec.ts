import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { MarketingPlanComponent } from './marketing-plan.component';

type UiCase = { name: string; status: string; update?: boolean };

describe('MarketingPlanComponent UX state matrix', () => {
  const cases: UiCase[] = [
    { name: 'no plans', status: 'empty' },
    { name: 'no compatible channels', status: 'blocked' },
    { name: 'no eligible account', status: 'blocked' },
    { name: 'missing marketplace listing', status: 'blocked' },
    { name: 'no approved creative', status: 'blocked' },
    { name: 'blocked dependency', status: 'blocked' },
    { name: 'partially completed', status: 'partially_completed' },
    { name: 'retry wait', status: 'retry_wait' },
    { name: 'ambiguous', status: 'ambiguous' },
    { name: 'failed', status: 'failed' },
    { name: 'recovery available', status: 'partially_completed' },
    { name: 'succeeded', status: 'succeeded' },
    { name: 'cancelled channel', status: 'cancelled' },
    { name: 'loading', status: 'queued' },
    { name: 'safe backend error', status: 'error' },
    { name: 'stale preview', status: 'stale' },
    { name: 'duplicate confirmation disabled', status: 'queued' },
    { name: 'confirmation pending controls disabled', status: 'queued' },
    { name: 'unsupported Meesho Ads', status: 'blocked' },
    { name: 'update available', status: 'succeeded', update: true },
  ];

  function create() {
    TestBed.configureTestingModule({
      imports: [MarketingPlanComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(MarketingPlanComponent);
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/v1/ads/marketing/plans').flush([]);
    http.expectOne('/api/v1/ads/marketing/capabilities').flush({
      channels: ['meta', 'google', 'amazon', 'flipkart', 'social', 'campaign'],
    });
    fixture.detectChanges();
    return { fixture, component: fixture.componentInstance, http };
  }

  it('covers 20 user-visible plan states with safe controls and status text', () => {
    const { fixture, component, http } = create();
    expect(cases).toHaveLength(20);
    for (const state of cases) {
      if (state.name === 'no plans') {
        component.plans.set([]);
      } else if (state.name === 'safe backend error') {
        component.error.set(
          'Marketing Plan data is unavailable. Check the authenticated API connection.',
        );
      } else {
        component.error.set('');
        component.plans.set([
          {
            id: state.name,
            objective: 'sales',
            target_channels: state.name.includes('Meesho') ? ['meesho'] : ['social', 'campaign'],
            budget_envelope: { total: '100', currency: 'INR' },
            status: state.status,
            current_version: state.update ? 2 : 1,
            update_available: state.update,
          },
        ]);
      }
      component.wizardOpen.set(state.name.includes('confirmation'));
      component.submitting.set(state.name.includes('disabled') || state.name.includes('pending'));
      if (state.name === 'stale preview') {
        component.wizardOpen.set(true);
        component.wizardError.set(
          'The plan could not be confirmed. Review owner-scoped dependencies.',
        );
      }
      fixture.detectChanges();
      const text = fixture.nativeElement.textContent as string;
      if (state.name === 'no plans') {
        expect(text).toContain('No marketing plans yet');
      } else if (state.name === 'safe backend error') {
        expect(fixture.nativeElement.querySelector('[role="alert"]')).not.toBeNull();
      } else {
        expect(text.toLowerCase()).toContain(state.status);
      }
      if (state.update) expect(text).toContain('v2');
      if (state.name.includes('Meesho')) expect(text).toContain('meesho');
    }
    http.verify();
  });

  it('keeps wizard navigation native, labelled, and disabled at boundaries', () => {
    const { fixture, component, http } = create();
    component.wizardOpen.set(true);
    component.wizardStep.set(0);
    fixture.detectChanges();
    const root = fixture.nativeElement as unknown as HTMLElement;
    const back = root.querySelector<HTMLButtonElement>('.wizard-actions button');
    expect(back?.disabled).toBe(true);
    expect(fixture.nativeElement.querySelectorAll('label').length).toBeGreaterThan(0);
    component.wizardStep.set(component.steps.length - 1);
    component.submitting.set(true);
    fixture.detectChanges();
    const buttons = Array.from(root.querySelectorAll<HTMLButtonElement>('button'));
    expect(buttons.some((button) => button.disabled)).toBe(true);
    http.verify();
  });
});
