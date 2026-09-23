import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { CrossMarketplaceSupplierComponent } from './cross-marketplace-supplier.component';

const base = '/api/v1/intelligence/cross-marketplace/suppliers';

describe('CrossMarketplaceSupplierComponent', () => {
  it('presents provider truth, observed evidence, and comparison trade-offs without a winner', async () => {
    TestBed.configureTestingModule({
      imports: [CrossMarketplaceSupplierComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(CrossMarketplaceSupplierComponent);
    const http = TestBed.inject(HttpTestingController);
    http.expectOne(base).flush([
      {
        id: 'supplier-1',
        display_name: 'Fixture supplier',
        aliases: [],
        identity: { state: 'CONFIRMED', rationale: 'matched', supplier_ids: [] },
        identity_state: 'CONFIRMED',
        confidence_score: 0.8,
        source_diversity_score: 0.7,
        freshness_status: 'CURRENT',
        source_diversity: {
          independent_source_count: 2,
          source_diversity_score: 0.7,
          provider_classes: ['IndiaMART'],
        },
        freshness: { overall: 'CURRENT', sources: [] },
        commercial: { moq: 500, currency: 'INR' },
        verification: [],
        capabilities: [],
        facilities: [],
        certifications: [],
        risk: { level: 'UNKNOWN', dimensions: [] },
        confidence: { classification: 'MODERATE' },
        contradictions: [],
        provider_mode: 'LOCAL_FIXTURE',
      },
    ]);
    http.expectOne(base + '/operations').flush({
      canonical_supplier_count: 1,
      multi_source_supplier_count: 1,
      single_source_supplier_count: 0,
      conflict_count: 0,
      stale_supplier_count: 0,
      high_risk_count: 0,
      pending_review_count: 0,
      provider_coverage: ['IndiaMART'],
      provider_mode: 'LOCAL_FIXTURE',
    });
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.textContent).toContain('Provider mode: LOCAL_FIXTURE');
    expect(root.textContent).toContain('Find suppliers');
    expect(root.textContent?.toLowerCase()).toContain('no supplier is selected');
    const inspect = Array.from(root.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('Inspect'),
    ) as HTMLButtonElement;
    inspect.click();
    fixture.detectChanges();
    expect(root.textContent).toContain('Observed supplier facts');
    expect(root.textContent).toContain('OBSERVED');
    expect(root.textContent).toContain('no comparison winner is inferred');
    http.verify();
  });
});
