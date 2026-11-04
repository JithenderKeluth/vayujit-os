import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter, Router } from '@angular/router';
import { vi } from 'vitest';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';

import { IntelligenceService } from './intelligence.service';
import { SourcingWorkspaceComponent } from './sourcing-workspace.component';
import { ProductOpportunityService } from './product-opportunity.service';
import { CrossMarketplaceService } from './cross-marketplace.service';
import { BehaviorSubject } from 'rxjs';

describe('SourcingWorkspaceComponent', () => {
  it('keeps unknown seller economics blank and blocks incomplete calculation', async () => {
    const service: Partial<IntelligenceService> = {
      sourcingOverview: vi.fn().mockResolvedValue({}),
      sourcingRequirements: vi.fn().mockResolvedValue({ items: [] }),
      sourcingRFQs: vi.fn().mockResolvedValue({ items: [] }),
    };
    await TestBed.configureTestingModule({
      imports: [SourcingWorkspaceComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: IntelligenceService, useValue: service },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(SourcingWorkspaceComponent);
    const component = fixture.componentInstance;
    expect(component.scenario.inputs.unit_supplier_price).toBeNull();
    expect(component.scenario.inputs.freight).toBeNull();
    expect(component.scenario.inputs.selling_price).toBeNull();
    expect(component.quote.unit_price).toBeNull();
    await component.createQuote();
    expect(component.error()).toContain('Enter a supplier unit price');
    await component.calculate();
    expect(component.error()).toContain('Enter supplier price, freight, and selling price');
    expect(service.sourcingRequirements).toHaveBeenCalled();
  });

  it('uses canonical Product/source identities, scoped records, exact response envelopes and persistent quote replay keys', async () => {
    const params = new BehaviorSubject(
      convertToParamMap({ opportunity_id: 'op-a', supplier_id: 'canonical-a' }),
    );
    const req = { id: 'requirement-a', product_id: 'product-a', current_version: 3 };
    const rfq = {
      id: 'rfq-a',
      requirement_id: 'requirement-a',
      version: 1,
      title: 'Local',
      dispatch_status: 'not_sent',
    };
    const quote = { id: 'quote-a', rfq_id: 'rfq-a', supplier_id: 'source-a' };
    const service = {
      sourcingOverview: vi.fn().mockResolvedValue({}),
      sourcingRequirements: vi
        .fn()
        .mockResolvedValue({ items: [{ id: 'other', product_id: 'product-b' }, req] }),
      sourcingRFQs: vi
        .fn()
        .mockResolvedValue({ items: [{ id: 'other-rfq', requirement_id: 'other' }, rfq] }),
      sourcingQuotes: vi
        .fn()
        .mockResolvedValue({ items: [{ id: 'other-quote', rfq_id: 'other-rfq' }, quote] }),
      createSourcingRequirement: vi.fn().mockResolvedValue({ requirement: req }),
      createRFQ: vi.fn().mockResolvedValue({ rfq }),
      createSourcingQuote: vi.fn().mockResolvedValue(quote),
    };
    await TestBed.configureTestingModule({
      imports: [SourcingWorkspaceComponent],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: { queryParamMap: params, snapshot: { queryParamMap: params.value } },
        },
        { provide: IntelligenceService, useValue: service },
        {
          provide: ProductOpportunityService,
          useValue: {
            get: vi.fn().mockResolvedValue({
              id: 'op-a',
              product_id: 'product-a',
              name: 'Bottle',
              category: 'Home',
              target_marketplace: 'AMAZON_IN',
              target_region: 'IN',
              lifecycle_status: 'active',
            }),
          },
        },
        {
          provide: CrossMarketplaceService,
          useValue: {
            researchResults: vi.fn().mockResolvedValue({ suppliers: [{ id: 'canonical-a' }] }),
            detail: vi.fn().mockResolvedValue({
              display_name: 'Synthetic',
              identity: { supplier_ids: ['source-a'] },
            }),
          },
        },
      ],
    }).compileComponents();
    vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const fixture = TestBed.createComponent(SourcingWorkspaceComponent);
    const component = fixture.componentInstance;
    await vi.waitFor(() => {
      expect(component.busy()).toBe(false);
    });
    expect(component.requirements()).toEqual([req]);
    expect(component.supplierOptions()[0].id).toBe('source-a');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('AVAILABLE FOR REVIEW');
    expect(fixture.nativeElement.textContent).not.toContain('SHORTLISTED');
    expect(component.quote.supplier_id).toBe(''); // No silent supplier choice.
    await component.createRequirement();
    expect(service.createSourcingRequirement.mock.calls[0][0]).toMatchObject({
      product_id: 'product-a',
      opportunity_id: null,
    });
    component.rfq.supplier_ids_text = 'source-a';
    await component.createRFQ();
    expect(service.createRFQ.mock.calls[0][0].requirement_version).toBe(3);
    expect(component.rfqId()).toBe('rfq-a');
    expect(component.quotes()).toEqual([quote]);
    expect(component.decision.quote_id).toBe('');
    component.quote.supplier_id = 'source-a';
    component.quote.quote_reference = 'Synthetic';
    component.quote.unit_price = 0;
    component.quote.moq = 1;
    await component.createQuote();
    await component.createQuote();
    expect(service.createSourcingQuote).toHaveBeenCalledTimes(2);
    expect(service.createSourcingQuote.mock.calls[0][0].idempotency_key).toBe(
      service.createSourcingQuote.mock.calls[1][0].idempotency_key,
    );
    expect(component.quote.unit_price).toBe(0);
    expect(component.quoteValidity({ valid_until: '2000-01-01T00:00:00Z' })).toContain('EXPIRED');
    expect(component.quoteValidity({ valid_until: null })).toContain('UNKNOWN');
    await component.selectRFQ('other-rfq');
    expect(component.scopeError()).toContain('does not belong');
    component.busy.set(true);
    params.next(convertToParamMap({}));
    expect(component.busy()).toBe(false);
    expect(component.scopeError()).toBe('');
    expect(component.selectedContext()).toBeNull();
    expect(component.quote.supplier_id).toBe('');
  });
});
