import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import {
  ActivatedRoute,
  convertToParamMap,
  provideRouter,
  Router,
  RouterLink,
} from '@angular/router';
import { BehaviorSubject } from 'rxjs';
import { vi } from 'vitest';
import { environment } from '../../environments/environment';
import { CrossMarketplaceService } from './cross-marketplace.service';
import { CrossMarketplaceSupplierComponent } from './cross-marketplace-supplier.component';
import { SourcingEconomicsWorkspaceComponent } from './sourcing-economics-workspace.component';
import { SupplierDueDiligenceComponent } from './supplier-due-diligence.component';
import { supplierEvidenceOrigin } from './supplier-evidence-origin';

function configure() {
  TestBed.configureTestingModule({
    providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
  });
}

describe('WP1 supplier-to-economics contracts', () => {
  it('keeps economics jump navigation on the current route with scope queries', () => {
    configure();
    const fixture = TestBed.createComponent(SourcingEconomicsWorkspaceComponent);
    const c = fixture.componentInstance;
    vi.spyOn(c, 'ngOnInit').mockImplementation(() => {});
    fixture.detectChanges();
    c.opportunityId = 'op-a';
    c.scopeLoading.set(false);
    c.scopeError.set('');
    fixture.detectChanges();
    const jump = fixture.debugElement
      .queryAll(By.directive(RouterLink))
      .find((el) => el.nativeElement.textContent.trim() === 'Set up economic inputs');
    expect(jump).toBeDefined();
    const link = jump!.injector.get(RouterLink);
    expect(link.queryParamsHandling).toBe('preserve');
    expect(link.fragment).toBe('context-title');
  });
  it('retains explicit synthetic source markers, including mixed sources', () => {
    expect(
      supplierEvidenceOrigin({
        freshness: {
          sources: [{ external_id: 'real-reference' }, { external_id: 'fixture:local' }],
        },
      }),
    ).toContain('synthetic fixture evidence');
    expect(
      supplierEvidenceOrigin({
        freshness: { sources: [{ external_id: 'source-url', synthetic: true }] },
      }),
    ).toContain('synthetic fixture evidence');
  });
  it('does not upgrade missing provenance to real verification', () => {
    expect(supplierEvidenceOrigin(null)).toContain('No live supplier verification');
  });
  it('does not upgrade non-fixture source references to verified evidence', () => {
    expect(
      supplierEvidenceOrigin({ freshness: { sources: [{ external_id: 'source-reference' }] } }),
    ).toContain('No live supplier verification');
  });
  it('clears unsaved assumptions and changes replay identity when route scope changes', async () => {
    configure();
    const params = new BehaviorSubject(
      convertToParamMap({ opportunity_id: 'op-a', supplier_id: 'supplier-a' }),
    );
    TestBed.overrideProvider(ActivatedRoute, {
      useValue: { queryParamMap: params, snapshot: { queryParamMap: params.value } },
    });
    const c = TestBed.createComponent(SourcingEconomicsWorkspaceComponent).componentInstance;
    c.ngOnInit();
    const key = c.draft.idempotency_key;
    c.draft.base_currency = 'INR';
    c.draft.target_quantity = 500;
    params.next(convertToParamMap({ opportunity_id: 'op-b', supplier_id: 'supplier-b' }));
    expect(c.draft.idempotency_key).not.toBe(key);
    expect(c.draft.base_currency).toBe('');
    expect(c.draft.target_quantity).toBeNull();
    expect(c.scopeLoading()).toBe(true);
    await c.createContext();
    TestBed.inject(HttpTestingController).expectNone(
      `${environment.apiUrl}/intelligence/sourcing-economics/contexts`,
    );
    params.complete();
  });
  for (const mode of ['LOCAL_FIXTURE', 'LIVE_READ_ONLY'] as const) {
    it(`submits the projected ${mode} mode and suppresses an in-flight duplicate`, async () => {
      configure();
      const c = TestBed.createComponent(CrossMarketplaceSupplierComponent).componentInstance;
      c.productContext.set({
        opportunityId: 'op-a',
        product: 'Bottle',
        category: 'Kids',
        subcategory: '',
        marketplace: 'AMAZON_IN',
        market: 'IN',
        region: 'IN',
        researchTerms: '',
      });
      c.researchQuery = 'Bottle';
      c.researchMode = mode;
      const service = TestBed.inject(CrossMarketplaceService);
      const research = vi.spyOn(service, 'research').mockResolvedValue({});
      vi.spyOn(service, 'reconcile').mockResolvedValue([]);
      vi.spyOn(c, 'load').mockResolvedValue();
      vi.spyOn(service, 'researchResults').mockResolvedValue({
        execution_mode: mode,
        suppliers: [],
      });
      const first = c.startResearch();
      await c.startResearch();
      await first;
      expect(research).toHaveBeenCalledTimes(1);
      expect(research.mock.calls[0][0]['mode']).toBe(mode);
      expect(research.mock.calls[0][0]['idempotency_key']).toContain(mode);
    });
  }

  it('does not discover with an unknown or disabled projected mode', async () => {
    configure();
    const c = TestBed.createComponent(CrossMarketplaceSupplierComponent).componentInstance;
    c.productContext.set({
      opportunityId: 'op-a',
      product: 'Bottle',
      category: 'Kids',
      subcategory: '',
      marketplace: '',
      market: '',
      region: '',
      researchTerms: '',
    });
    c.researchQuery = 'Bottle';
    const research = vi.spyOn(TestBed.inject(CrossMarketplaceService), 'research');
    await c.startResearch();
    expect(research).not.toHaveBeenCalled();
  });

  it('sends typed canonical identities and puts the saved context in the reload URL', async () => {
    configure();
    const c = TestBed.createComponent(SourcingEconomicsWorkspaceComponent).componentInstance;
    c.opportunityId = 'op-a';
    c.supplierId = 'canonical-a';
    c.draft.base_currency = 'INR';
    const nav = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    const http = TestBed.inject(HttpTestingController);
    const first = c.createContext();
    await c.createContext();
    const request = http.expectOne(
      `${environment.apiUrl}/intelligence/sourcing-economics/contexts`,
    );
    expect(request.request.body).toEqual(
      expect.objectContaining({
        product_opportunity_id: 'op-a',
        canonical_supplier_id: 'canonical-a',
      }),
    );
    expect(request.request.body.opportunity_id).toBeUndefined();
    request.flush({
      context: {
        id: 'saved-a',
        product_opportunity_id: 'op-a',
        canonical_supplier_id: 'canonical-a',
      },
    });
    await first;
    expect(nav.mock.calls[0][1]?.queryParams).toEqual({
      economic_context_id: 'saved-a',
      opportunity_id: 'op-a',
      supplier_id: 'canonical-a',
    });
    http.verify();
  });

  it('does not save missing or stale context and preserves it after backend rejection', async () => {
    configure();
    const c = TestBed.createComponent(SourcingEconomicsWorkspaceComponent).componentInstance;
    const http = TestBed.inject(HttpTestingController);
    await c.createContext();
    http.expectNone(`${environment.apiUrl}/intelligence/sourcing-economics/contexts`);
    c.opportunityId = 'op-a';
    c.scopeError.set('Stale');
    await c.createContext();
    http.expectNone(`${environment.apiUrl}/intelligence/sourcing-economics/contexts`);
    c.scopeError.set('');
    c.supplierId = 'supplier-a';
    const save = c.createContext();
    http
      .expectOne(`${environment.apiUrl}/intelligence/sourcing-economics/contexts`)
      .flush({}, { status: 409, statusText: 'Conflict' });
    await save;
    expect(c.context()).toBeNull();
    expect(c.supplierId).toBe('supplier-a');
    expect(c.error()).toContain('could not be saved');
  });

  it('distinguishes unassessed from zero gaps and assesses only existing evidence once in flight', async () => {
    configure();
    const c = TestBed.createComponent(SupplierDueDiligenceComponent).componentInstance;
    const context = {
      id: 'dd-a',
      supplier_id: 'supplier-a',
      status: 'OPEN',
      readiness: 'NOT_ASSESSED',
      assessment_version: 0,
    };
    c.contexts = [context];
    expect(c.isAssessed(context)).toBe(false);
    vi.spyOn(c as unknown as { loadContexts(): Promise<void> }, 'loadContexts').mockResolvedValue();
    const first = c.assessEvidence(context);
    await c.assessEvidence(context);
    const http = TestBed.inject(HttpTestingController);
    const request = http.expectOne(
      `${environment.apiUrl}/intelligence/supplier-due-diligence/contexts/dd-a/assess`,
    );
    expect(request.request.body).toEqual({});
    expect(request.request.withCredentials).toBe(true);
    request.flush({ assessment_version: 1 });
    await first;
    expect(c.assessmentMessage).toContain('Assessment saved');
    expect(c.assessingId).toBe('');
    http.verify();
  });

  it('assessment failure keeps the supplier unassessed and avoids sensitive diagnostics', async () => {
    configure();
    const c = TestBed.createComponent(SupplierDueDiligenceComponent).componentInstance;
    const context = {
      id: 'dd-a',
      supplier_id: 'supplier-a',
      status: 'OPEN',
      readiness: 'NOT_ASSESSED',
    };
    c.contexts = [context];
    const action = c.assessEvidence(context);
    TestBed.inject(HttpTestingController)
      .expectOne(`${environment.apiUrl}/intelligence/supplier-due-diligence/contexts/dd-a/assess`)
      .flush({ detail: 'private token' }, { status: 500, statusText: 'Error' });
    await action;
    expect(c.isAssessed(context)).toBe(false);
    expect(c.error).toContain('context is unchanged');
    expect(c.error).not.toContain('private token');
  });
});
