import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { environment } from '../../environments/environment';
import { SupplierEngagementWorkspaceComponent } from './supplier-engagement-workspace.component';

describe('SupplierEngagementWorkspaceComponent', () => {
  function setup() {
    TestBed.configureTestingModule({
      imports: [SupplierEngagementWorkspaceComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    return {
      fixture: TestBed.createComponent(SupplierEngagementWorkspaceComponent),
      http: TestBed.inject(HttpTestingController),
    };
  }

  it('keeps engagement blocked when no product or supplier context is selected', () => {
    const { fixture, http } = setup();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Select a product opportunity first');
    http.verify();
  });

  it('prepares a canonical internal draft with stable idempotency and no send call', async () => {
    const { fixture, http } = setup();
    const component = fixture.componentInstance;
    component.opportunityId = 'opportunity-1';
    component.supplierId = 'supplier-1';
    component.contactId = 'contact-1';
    component.humanDecisionId = 'decision-1';
    component.requestedQuantity = 250;
    const promise = component.prepareDraft();
    const request = http.expectOne(`${environment.apiUrl}/intelligence/engagements`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toMatchObject({
      opportunity_id: 'opportunity-1',
      supplier_id: 'supplier-1',
      contact_id: 'contact-1',
      human_decision_id: 'decision-1',
      requested_quantity: 250,
    });
    expect(request.request.body.idempotency_key).toBe(
      'pruxe01e-engagement-opportunity-1-supplier-1',
    );
    request.flush({
      id: 'engagement-1',
      opportunity_id: 'opportunity-1',
      supplier_id: 'supplier-1',
      status: 'BLOCKED',
      blocking_reasons: [{ code: 'HUMAN_PROCEED_REQUIRED', message: 'Review is required.' }],
      current_draft: null,
      latest_approval: null,
      send_status: 'NOT_EXECUTED',
      safe_next_action: 'Review the decision.',
    });
    await Promise.resolve();
    const history = http.expectOne(
      `${environment.apiUrl}/intelligence/engagements/engagement-1/history`,
    );
    history.flush([]);
    await promise;
    expect(component.engagement()?.status).toBe('BLOCKED');
    expect(component.engagement()?.current_draft).toBeNull();
    http.verify();
    fixture.destroy();
  });

  it('renders supplier response evidence as reviewable and preserves unknowns', () => {
    const { fixture } = setup();
    const component = fixture.componentInstance;
    component.ngOnInit = () => undefined;
    component.opportunityId = 'opportunity-1';
    component.responses.set([
      {
        id: 'response-1',
        supplier_id: 'supplier-1',
        opportunity_id: 'opportunity-1',
        engagement_id: 'engagement-1',
        channel: 'EMAIL',
        sender_identity: null,
        received_at: '2026-10-10T00:00:00Z',
        raw_content: 'MOQ not provided',
        trust_environment: 'DETERMINISTIC_TEST',
        evidence_environment: 'DETERMINISTIC_TEST',
        correlation_state: 'CORRELATED',
        correlation_reason: 'Matched engagement scope',
        classification: 'QUOTE',
        extraction: {
          id: 'extraction-1',
          version: 1,
          status: 'PARTIAL',
          extracted_fields: {},
          unknown_fields: ['moq'],
          warnings: [],
          extraction_authority: 'DETERMINISTIC',
          source_raw_hash: 'hash',
        },
        reviews: [],
        promotion: null,
        safe_next_action: 'Review the extraction.',
      },
    ]);
    expect(component.listOrUnknown(['moq'])).toContain('moq');
    expect(component.responses().at(0)?.extraction?.unknown_fields).toEqual(['moq']);
    fixture.destroy();
  });
});
