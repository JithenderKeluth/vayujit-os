import { TestBed } from '@angular/core/testing';
import { PublicationPreviewComponent } from './publication-preview.component';

describe('PublicationPreviewComponent', () => {
  it('renders generated markup as inert text with the local mock warning', () => {
    const fixture = TestBed.createComponent(PublicationPreviewComponent);
    const component = fixture.componentRef;
    const content = {
      product_title: '<script>alert(1)</script>',
      short_description: 'Safe preview',
      long_description: '<b>not markup</b>',
      key_features: ['Fast'],
      seo_title: 'SEO',
      seo_description: 'SEO copy',
      social_caption: 'Caption',
      keywords: ['safe'],
      generation_summary: 'Mock',
    };
    component.setInput('artifact', {
      brand_name: 'Brand',
      version_number: 1,
      content,
    });
    component.setInput('product', {
      name: 'Product',
      sku: 'SKU',
      price_amount: '10.00',
      price_currency: 'USD',
    });
    component.setInput('destination', { name: 'Local Channel' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('<script>alert(1)</script>');
    expect(fixture.nativeElement.querySelector('script')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Local mock only');
  });
});
