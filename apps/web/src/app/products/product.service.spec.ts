import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ProductService } from './product.service';

const product = {
  id: 'product-1',
  brand_id: 'brand-1',
  brand_name: 'Acme',
  name: 'Widget',
  slug: 'widget',
  sku: 'SKU-1',
  product_type: 'physical' as const,
  status: 'draft' as const,
  short_description: 'A widget',
  description: null,
  category: 'Tools',
  tags: ['featured'],
  price_amount: '19.99',
  price_currency: 'USD',
  compare_at_price_amount: null,
  cost_amount: null,
  tax_code: null,
  barcode: null,
  weight_value: null,
  weight_unit: null,
  inventory_tracking_enabled: true,
  inventory_quantity: 5,
  low_stock_threshold: 1,
  is_featured: true,
  created_at: '2026-07-27T00:00:00Z',
  updated_at: '2026-07-27T00:00:00Z',
  archived_at: null,
};

describe('ProductService', () => {
  let service: ProductService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(ProductService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads active-brand product filters, sorting, and pagination', async () => {
    const loading = service.list({
      brandId: 'brand-1',
      search: 'widget',
      productType: 'physical',
      featured: true,
      sortBy: 'price',
      sortDirection: 'desc',
      page: 2,
    });
    const request = http.expectOne(
      (candidate) =>
        candidate.url.endsWith('/products') &&
        candidate.params.get('brand_id') === 'brand-1' &&
        candidate.params.get('search') === 'widget' &&
        candidate.params.get('product_type') === 'physical' &&
        candidate.params.get('featured') === 'true' &&
        candidate.params.get('sort_by') === 'price' &&
        candidate.params.get('sort_direction') === 'desc' &&
        candidate.params.get('page') === '2',
    );
    expect(request.request.withCredentials).toBe(true);
    request.flush({ items: [product], page: 2, page_size: 20, total: 21, pages: 2 });
    expect((await loading).items[0]?.price_amount).toBe('19.99');
  });

  it('keeps decimal money as strings during creation', async () => {
    const creating = service.create({
      brand_id: 'brand-1',
      name: 'Widget',
      product_type: 'physical',
      price_amount: '19.99',
      price_currency: 'USD',
    });
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/products');
    expect(request.request.body.price_amount).toBe('19.99');
    expect(typeof request.request.body.price_amount).toBe('string');
    request.flush(product);
    expect((await creating).id).toBe('product-1');
  });

  it('calls explicit lifecycle transition endpoints', async () => {
    const activation = service.activate(product.id);
    http
      .expectOne(`http://127.0.0.1:8000/api/v1/products/${product.id}/activate`)
      .flush({ ...product, status: 'active' });
    expect((await activation).status).toBe('active');

    const archive = service.archive(product.id);
    http
      .expectOne(`http://127.0.0.1:8000/api/v1/products/${product.id}/archive`)
      .flush({ ...product, status: 'archived' });
    expect((await archive).status).toBe('archived');
  });

  it('normalizes structured activation errors', () => {
    const error = new HttpErrorResponse({
      status: 409,
      error: {
        detail: {
          code: 'product_not_ready',
          message: 'Product does not meet activation requirements.',
          fields: ['description', 'price_amount'],
        },
      },
    });
    expect(ProductService.errorMessage(error)).toContain('Required: description, price_amount.');
  });
});
