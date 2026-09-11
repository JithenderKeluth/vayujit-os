import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ComponentFixtureAutoDetect, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { SupplierDueDiligenceComponent } from './supplier-due-diligence.component';

const base = '/api/v1/intelligence/supplier-due-diligence';
const statuses = [
  'MISSING',
  'WEAK',
  'STALE',
  'CONTRADICTORY',
  'INSUFFICIENT',
  'RESEARCHING',
  'RESOLVED',
  'WAIVED_BY_HUMAN',
  'BLOCKED',
  'REVIEW_REQUIRED',
];

function create() {
  TestBed.configureTestingModule({
    imports: [SupplierDueDiligenceComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      provideRouter([]),
      { provide: ComponentFixtureAutoDetect, useValue: false },
    ],
  });
  const fixture = TestBed.createComponent(SupplierDueDiligenceComponent);
  const component = fixture.componentInstance;
  component.ngOnInit = () => Promise.resolve();
  component.contexts = [
    {
      id: 'context-1',
      supplier_id: 'supplier-1',
      status: 'ACTIVE',
      readiness: 'REVIEW_REQUIRED',
      summary: { open_gaps: 1 },
      gaps: [
        {
          id: 'gap-1',
          dimension: 'identity',
          classification: 'REQUIRED',
          status: 'MISSING',
          severity: 'HIGH',
        },
      ],
      plans: [],
    },
  ];
  return { fixture, component, http: TestBed.inject(HttpTestingController) };
}

describe('SupplierDueDiligenceComponent', () => {
  it('maps all semantic states and records Review Evidence', async () => {
    const { component, http } = create();
    for (const status of statuses) {
      expect(component.semanticStatus(status)).toBe(
        status === 'WAIVED_BY_HUMAN'
          ? 'WAIVED BY HUMAN'
          : status === 'REVIEW_REQUIRED'
            ? 'REVIEW REQUIRED'
            : status,
      );
    }
    const review = component.reviewEvidence('gap-1');
    http.expectOne(`${base}/contexts/context-1/gaps/gap-1`).flush({ id: 'gap-1' });
    await review;
    expect(component.reviewedGapId).toBe('gap-1');
    http.verify();
  });

  it('requires a waiver reason and sends a successful waiver', async () => {
    const { component, http } = create();
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('');
    await component.act('gap-1', 'waive_gap');
    http.expectNone(`${base}/gaps/gap-1/waive_gap`);
    prompt.mockReturnValue('Reviewed by owner');
    const action = component.act('gap-1', 'waive_gap');
    const request = http.expectOne(`${base}/gaps/gap-1/waive_gap`);
    expect(request.request.body).toEqual({ reason: 'Reviewed by owner' });
    request.flush({ status: 'WAIVED_BY_HUMAN' });
    await action;
    expect(component.error).toBe(false);
    expect(component.semanticStatus('WAIVED_BY_HUMAN')).toBe('WAIVED BY HUMAN');
    http.verify();
  });

  it('surfaces server rejection without exposing diagnostics', async () => {
    const { component, http } = create();
    vi.spyOn(window, 'prompt').mockReturnValue('Reviewed by owner');
    const action = component.act('gap-1', 'waive_gap');
    const request = http.expectOne(`${base}/gaps/gap-1/waive_gap`);
    request.flush(
      { detail: 'SQL traceback token' },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    await action;
    expect(component.error).toBe(true);
    expect(component.reviewedGapId).toBeNull();
    http.verify();
  });
});
