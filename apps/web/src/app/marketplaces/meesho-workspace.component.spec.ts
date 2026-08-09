import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute } from '@angular/router';
import { TestBed } from '@angular/core/testing';

import { MeeshoWorkspaceComponent } from './meesho-workspace.component';

describe('MeeshoWorkspaceComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MeeshoWorkspaceComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => null } } } },
      ],
    }).compileComponents();
  });

  function createComponent() {
    return TestBed.createComponent(MeeshoWorkspaceComponent).componentInstance;
  }
  it('builds deterministic six-row matrix for three sizes and two colors', () => {
    const component = createComponent();
    component.matrixDimensionsText = 'Size=S|M|L;Color=Red|Blue';
    component.buildVariantMatrix();
    expect(component.variants().map((row) => row.options)).toEqual([
      'Size=S, Color=Red',
      'Size=S, Color=Blue',
      'Size=M, Color=Red',
      'Size=M, Color=Blue',
      'Size=L, Color=Red',
      'Size=L, Color=Blue',
    ]);
    expect(new Set(component.variants().map((row) => row.stable_variant_key)).size).toBe(6);
  });

  it('preserves matching values and rejects matrices above 100 rows', () => {
    const component = createComponent();
    component.matrixDimensionsText = 'Color=Red|Blue';
    component.buildVariantMatrix();
    component.variants()[0].sku = 'MS-RED';
    component.matrixDimensionsText = 'Color=Red|Blue|Green';
    component.buildVariantMatrix();
    expect(component.variants()[0].sku).toBe('MS-RED');
    component.matrixDimensionsText = 'A=1|2|3|4|5|6|7|8|9|10;B=1|2|3|4|5|6|7|8|9|10;C=1|2';
    component.buildVariantMatrix();
    expect(component.matrixError()).toContain('at most 100');
  });
});
