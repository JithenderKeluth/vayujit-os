import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { BusinessEntitySelectorsComponent } from './business-entity-selectors.component';

describe('BusinessEntitySelectorsComponent', () => {
  it('loads owner-scoped business labels and emits canonical ids', async () => {
    TestBed.configureTestingModule({
      imports: [BusinessEntitySelectorsComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const fixture = TestBed.createComponent(BusinessEntitySelectorsComponent);
    const component = fixture.componentInstance;
    component.showBrand = true;
    const http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http
      .expectOne((request) => request.url.endsWith('/products'))
      .flush({
        items: [
          { id: 'product-1', name: 'Travel mug', sku: 'MUG-1', category: 'Home', status: 'active' },
        ],
        page: 1,
        page_size: 50,
        total: 1,
        pages: 1,
      });
    http
      .expectOne((request) => request.url.endsWith('/brands'))
      .flush({
        items: [{ id: 'brand-1', name: 'Heritage', status: 'active' }],
        page: 1,
        page_size: 50,
        total: 1,
        pages: 1,
      });
    await fixture.whenStable();
    fixture.detectChanges();
    const productChanges: string[] = [];
    component.productIdChange.subscribe((value) => productChanges.push(value));
    const productSelect = fixture.nativeElement.querySelector('select') as HTMLSelectElement;
    productSelect.value = 'product-1';
    productSelect.dispatchEvent(new Event('change'));
    expect(productChanges).toEqual(['product-1']);
    expect(fixture.nativeElement.textContent).toContain('Travel mug');
    expect(fixture.nativeElement.textContent).toContain('Heritage');
    http.verify();
  });
});
