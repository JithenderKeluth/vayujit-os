import { ActivatedRoute, Router } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { AIService } from '../ai/ai.service';
import { BrandService } from '../brands/brand.service';
import { ProductService } from '../products/product.service';
import { PublishingService } from './publishing.service';
import { PublishNewComponent } from './publish-new.component';

describe('PublishNewComponent selection rules', () => {
  let component: PublishNewComponent;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        {
          provide: PublishingService,
          useValue: { publish: () => Promise.resolve({ id: 'execution-1' }) },
        },
        { provide: AIService, useValue: {} },
        { provide: BrandService, useValue: {} },
        { provide: ProductService, useValue: {} },
        { provide: Router, useValue: { navigate: () => Promise.resolve(true) } },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: { get: () => null } } } },
      ],
    });
    component = TestBed.createComponent(PublishNewComponent).componentInstance;
    component.brandId = 'b1';
    component.productId = 'p1';
    component.products.set([
      { id: 'p1', brand_id: 'b1', status: 'active', name: 'Eligible' },
      { id: 'p2', brand_id: 'b1', status: 'archived', name: 'Archived' },
    ] as never);
    component.artifacts.set([
      { artifact_id: 'a1', product_id: 'p1', artifact_status: 'approved' },
      { artifact_id: 'a2', product_id: 'p1', artifact_status: 'rejected' },
    ] as never);
    component.destinations.set([
      { id: 'd1', status: 'active', brand_id: null },
      { id: 'd2', status: 'active', brand_id: 'b2' },
      { id: 'd3', status: 'disabled', brand_id: 'b1' },
    ] as never);
  });
  it('excludes archived Products and non-approved Artifacts', () => {
    expect(component.eligibleProducts().map((item) => item.id)).toEqual(['p1']);
    expect(component.eligibleArtifacts().map((item) => item.artifact_id)).toEqual(['a1']);
  });
  it('keeps only active destinations compatible with the selected Brand', () => {
    expect(component.compatibleDestinations().map((item) => item.id)).toEqual(['d1']);
  });
  it('resets downstream selections when Brand changes', () => {
    component.productId = 'p1';
    component.artifactId = 'a1';
    component.destinationId = 'd1';
    component.confirmed = true;
    component.brandChanged();
    expect(component.productId).toBe('');
    expect(component.artifactId).toBe('');
    expect(component.destinationId).toBe('');
    expect(component.confirmed).toBe(false);
  });
  it('builds bounded structured variant rows with Product price defaults', () => {
    component.addVariant();
    expect(component.shopifyVariants).toHaveLength(1);
    expect(component.shopifyVariants[0].local_key).toBe('variant-1');
    component.removeVariant(0);
    expect(component.shopifyVariants).toEqual([]);
  });
  it('preserves Shopify media selection order', () => {
    component.toggleMedia('media-2');
    component.toggleMedia('media-1');
    expect(component.selectedMediaIds).toEqual(['media-2', 'media-1']);
    component.toggleMedia('media-2');
    expect(component.selectedMediaIds).toEqual(['media-1']);
  });
});
