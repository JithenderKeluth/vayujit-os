import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import * as axe from 'axe-core';
import { IntelligenceService } from './intelligence.service';
import { ProductDiscoveryReviewComponent } from './product-discovery-review.component';

const details = {
  queries: [{ query: 'sports and outdoor fitness product detail India', status: 'COMPLETED' }],
  fetches: [
    {
      url: 'https://example.org/product/band',
      domain: 'example.org',
      status: 'FAILED',
      failure: 'External source approval is required before fetching.',
    },
  ],
  observability: { urls_fetched: 6 }, // Legacy attempted-count bug must not be displayed.
};

describe('ProductDiscoveryReviewComponent', () => {
  const service = { approveExternalSource: vi.fn(), externalSourceProfiles: vi.fn() };
  beforeEach(async () => {
    vi.resetAllMocks();
    service.externalSourceProfiles.mockResolvedValue([]);
    service.approveExternalSource.mockResolvedValue({ enabled: true });
    await TestBed.configureTestingModule({
      imports: [ProductDiscoveryReviewComponent],
      providers: [{ provide: IntelligenceService, useValue: service }],
    }).compileComponents();
  });

  async function render(value: Record<string, unknown> = details) {
    const fixture = TestBed.createComponent(ProductDiscoveryReviewComponent);
    fixture.componentRef.setInput('details', value);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture;
  }

  it('shows legacy source blockers and truthful successful-fetch counters', async () => {
    const fixture = await render();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('0 successful page fetches');
    expect(root.textContent).toContain('Review blocked sources');
    expect(root.textContent).not.toContain('6 successful');
    expect(fixture.componentInstance.canApprove()).toBe(false);
    expect(service.approveExternalSource).not.toHaveBeenCalled();
  });

  it('requires all policy confirmations, records an audit purpose, and never starts discovery', async () => {
    const fixture = await render();
    const component = fixture.componentInstance;
    await component.approve();
    expect(service.approveExternalSource).not.toHaveBeenCalled();
    component.robotsReviewed = component.termsReviewed = true;
    component.reason = 'Reviewed permitted read-only policy';
    expect(component.canApprove()).toBe(false);
    component.accessReviewed = true;
    await component.approve();
    expect(service.approveExternalSource).toHaveBeenCalledExactlyOnceWith(
      'example.org',
      `${component.auditPurpose} Note: Reviewed permitted read-only policy`,
    );
    expect(component.message()).toContain('No page was fetched');
    expect(component.domains()).toEqual([]);
    expect(component.canApprove()).toBe(false);
  });

  it('preserves the pending source after an authorization failure', async () => {
    service.approveExternalSource.mockRejectedValue({ status: 401 });
    const fixture = await render();
    const component = fixture.componentInstance;
    component.robotsReviewed = component.termsReviewed = component.accessReviewed = true;
    component.reason = 'Reviewed policy';
    await component.approve();
    expect(component.domains()).toEqual(['example.org']);
    expect(component.error()).toContain('No approval is confirmed');
    expect(component.busy()).toBe(false);
  });

  it('reconstructs existing canonical approvals on refresh', async () => {
    service.externalSourceProfiles.mockResolvedValue([
      {
        enabled: true,
        robots_policy: 'APPROVED',
        terms_status: 'APPROVED',
        access_classification: 'APPROVED',
        blocked_domains: [],
        approved_domains: ['example.org'],
      },
    ]);
    const fixture = await render();
    expect(fixture.componentInstance.domains()).toEqual([]);
    expect(fixture.nativeElement.textContent).toContain('Recorded source approvals are available');
    expect(service.approveExternalSource).not.toHaveBeenCalled();
  });

  it('does not trust disabled or incomplete approvals', async () => {
    service.externalSourceProfiles.mockResolvedValue([
      {
        enabled: false,
        robots_policy: 'APPROVED',
        terms_status: 'APPROVED',
        access_classification: 'APPROVED',
        blocked_domains: [],
        approved_domains: ['example.org'],
      },
    ]);
    const fixture = await render();
    expect(fixture.componentInstance.domains()).toEqual(['example.org']);
  });

  it('fails closed when current approval state cannot be loaded', async () => {
    service.externalSourceProfiles.mockRejectedValue({ status: 500 });
    const fixture = await render();
    const component = fixture.componentInstance;
    component.robotsReviewed = component.termsReviewed = component.accessReviewed = true;
    component.reason = 'Reviewed policy';
    expect(component.canApprove()).toBe(false);
    expect(component.error()).toContain('could not be loaded');
  });

  it('does not render unsafe review links', async () => {
    const fixture = await render({
      ...details,
      fetches: [{ ...details.fetches[0], url: 'javascript:alert(1)' }],
    });
    expect(fixture.nativeElement.querySelector('a')).toBeNull();
  });

  it('clears HUMAN confirmations when the discovered domain changes', async () => {
    const fixture = await render();
    const component = fixture.componentInstance;
    component.robotsReviewed = component.termsReviewed = component.accessReviewed = true;
    component.reason = 'Reviewed the original domain';
    fixture.componentRef.setInput('details', {
      ...details,
      fetches: [
        {
          ...details.fetches[0],
          domain: 'other.example.org',
          url: 'https://other.example.org/product/new',
        },
      ],
    });
    fixture.detectChanges();
    expect(component.activeDomain()).toBe('other.example.org');
    expect(component.canApprove()).toBe(false);
    expect(component.reason).toBe('');
  });

  it('requires a fresh review for the next domain after recording one approval', async () => {
    const fixture = await render({
      ...details,
      fetches: [
        details.fetches[0],
        {
          ...details.fetches[0],
          domain: 'other.example.net',
          url: 'https://other.example.net/product/band',
        },
      ],
    });
    const component = fixture.componentInstance;
    component.robotsReviewed = component.termsReviewed = component.accessReviewed = true;
    component.reason = 'Reviewed first source';
    await component.approve();
    expect(component.activeDomain()).toBe('other.example.net');
    expect(component.canApprove()).toBe(false);
    component.robotsReviewed = component.termsReviewed = component.accessReviewed = true;
    component.reason = 'Reviewed second source independently';
    expect(component.canApprove()).toBe(true);
    await component.approve();
    expect(service.approveExternalSource).toHaveBeenLastCalledWith(
      'other.example.net',
      `${component.auditPurpose} Note: Reviewed second source independently`,
    );
  });

  it('accepts an empty optional note while retaining the required audit purpose', async () => {
    const fixture = await render();
    const component = fixture.componentInstance;
    component.robotsReviewed = component.termsReviewed = component.accessReviewed = true;
    expect(component.reason).toBe('');
    expect(component.canApprove()).toBe(true);
    await component.approve();
    expect(service.approveExternalSource).toHaveBeenCalledExactlyOnceWith(
      'example.org',
      component.auditPurpose,
    );
  });

  it('does not offer approval for a server-classified non-product surface', async () => {
    const fixture = await render({
      ...details,
      fetches: [
        {
          ...details.fetches[0],
          source_review_eligible: false,
          skip_reason: 'Search-results pages are not concrete products.',
        },
      ],
    });
    expect(fixture.componentInstance.domains()).toEqual([]);
    expect(fixture.nativeElement.querySelector('fieldset')).toBeNull();
  });

  it('has no serious or critical axe findings in the source-review state', async () => {
    const fixture = await render();
    const root = fixture.nativeElement as HTMLElement;
    document.body.append(root);
    const result = await axe.run(root, { rules: { 'color-contrast': { enabled: false } } });
    expect(
      result.violations.filter((violation) =>
        ['serious', 'critical'].includes(violation.impact || ''),
      ),
    ).toEqual([]);
    root.remove();
  });
});
