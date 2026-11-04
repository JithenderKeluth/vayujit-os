import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { of } from 'rxjs';
import { CatalogWorkspaceComponent } from './catalog-workspace.component';
import { CatalogService } from './catalog.service';
import { ProductService } from '../products/product.service';

describe('Catalog canonical economics presentation', () => {
  it('uses canonical base_currency and preserves the opportunity link without inventing INR', async () => {
    const api = {
      getProduct: vi.fn().mockResolvedValue({
        product: { id: 'product-a', name: 'Synthetic', status: 'draft', brand_name: 'QA' },
        lineage: { opportunity_id: 'op-a', provenance_json: {} },
        variants: [],
        images: [],
        supplier_associations: [],
        listing_drafts: [],
      }),
      readiness: vi.fn().mockResolvedValue(null),
      media: vi.fn().mockResolvedValue({ items: [] }),
      economics: vi.fn().mockResolvedValue({
        available: true,
        opportunity_id: 'op-a',
        projection: { base_currency: 'INR', status: 'PARTIAL' },
      }),
    };
    await TestBed.configureTestingModule({
      imports: [CatalogWorkspaceComponent],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            paramMap: of(convertToParamMap({ id: 'product-a' })),
            snapshot: {
              paramMap: convertToParamMap({ id: 'product-a' }),
              queryParamMap: convertToParamMap({}),
            },
          },
        },
        { provide: CatalogService, useValue: api },
        { provide: ProductService, useValue: {} },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(CatalogWorkspaceComponent);
    await vi.waitFor(() => {
      expect(fixture.componentInstance.economicsLoading()).toBe(false);
    });
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const facts = root.querySelector('section[aria-labelledby="economics-title"]');
    expect(facts?.textContent).toMatch(/Currency\s*INR/);
    expect(facts?.querySelector('a')?.getAttribute('href')).toContain('opportunity_id=op-a');
    fixture.componentInstance.economics.set({
      product_id: 'product-a',
      available: true,
      opportunity_id: 'op-a',
      assessment_id: null,
      reason: null,
      projection: { status: 'PARTIAL' },
    });
    fixture.detectChanges();
    expect(facts?.textContent).toMatch(/Currency\s*UNKNOWN/);
  });
});
