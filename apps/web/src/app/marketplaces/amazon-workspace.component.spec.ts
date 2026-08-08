import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute } from '@angular/router';
import { TestBed } from '@angular/core/testing';

import { AmazonWorkspaceComponent } from './amazon-workspace.component';

describe('AmazonWorkspaceComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AmazonWorkspaceComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: { get: () => 'listing-1' } } },
        },
      ],
    }).compileComponents();
  });

  it('builds a bounded option matrix and preserves equivalent rows', () => {
    const fixture = TestBed.createComponent(AmazonWorkspaceComponent);
    const component = fixture.componentInstance;
    TestBed.inject(HttpTestingController)
      .expectOne('http://127.0.0.1:8000/api/v1/marketplaces/amazon/accounts')
      .flush([]);
    component.matrixDimensionsText = 'Color=Red|Blue;Size=S|M';
    component.buildVariantMatrix();
    expect(component.variants().length).toBe(4);
    expect(component.variants().map((row) => row.stable_variant_key)).toEqual([
      'matrix-1',
      'matrix-2',
      'matrix-3',
      'matrix-4',
    ]);
  });

  it('supports duplicate and remove controls without duplicate SKU assumptions', () => {
    const fixture = TestBed.createComponent(AmazonWorkspaceComponent);
    const component = fixture.componentInstance;
    TestBed.inject(HttpTestingController)
      .expectOne('http://127.0.0.1:8000/api/v1/marketplaces/amazon/accounts')
      .flush([]);
    component.addVariant();
    component.variants()[0].sku = 'SKU-1';
    component.duplicateVariant(0);
    expect(component.variants().length).toBe(2);
    expect(component.variants()[1].sku).toBe('SKU-1-COPY');
    component.removeVariant(1);
    expect(component.variants().length).toBe(1);
  });
});
