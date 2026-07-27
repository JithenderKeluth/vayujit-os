import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { BrandService } from './brand.service';

const brand = {
  id: 'brand-1',
  name: 'Acme',
  slug: 'acme',
  tagline: null,
  status: 'active' as const,
  website_url: null,
  primary_color: '#112233',
  secondary_color: null,
  is_active_context: true,
  created_at: '2026-07-27T00:00:00Z',
  updated_at: '2026-07-27T00:00:00Z',
  archived_at: null,
};

describe('BrandService', () => {
  let service: BrandService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(BrandService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads and restores the active brand from the API', async () => {
    const loading = service.loadActive();
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/brands/active');
    expect(request.request.withCredentials).toBe(true);
    request.flush(brand);
    await loading;
    expect(service.activeBrand()?.name).toBe('Acme');
    expect(service.activeLoaded()).toBe(true);
  });

  it('sends list filters and receives pagination metadata', async () => {
    const loading = service.list({
      search: 'acme',
      status: 'archived',
      includeArchived: true,
      page: 2,
      pageSize: 10,
    });
    const request = http.expectOne(
      (candidate) =>
        candidate.url.endsWith('/brands') &&
        candidate.params.get('search') === 'acme' &&
        candidate.params.get('status') === 'archived' &&
        candidate.params.get('include_archived') === 'true' &&
        candidate.params.get('page') === '2',
    );
    request.flush({ items: [], page: 2, page_size: 10, total: 0, pages: 0 });
    expect((await loading).page).toBe(2);
  });

  it('updates shell state after activation and active-brand archive', async () => {
    const activation = service.activate(brand.id);
    http.expectOne(`http://127.0.0.1:8000/api/v1/brands/${brand.id}/activate`).flush(brand);
    await activation;
    expect(service.activeBrand()?.id).toBe(brand.id);

    const archive = service.archive(brand.id);
    http
      .expectOne(`http://127.0.0.1:8000/api/v1/brands/${brand.id}/archive`)
      .flush({ ...brand, status: 'archived', is_active_context: false });
    await archive;
    expect(service.activeBrand()).toBeNull();
  });

  it('extracts duplicate-name API errors safely', () => {
    expect(
      BrandService.errorMessage(
        new HttpErrorResponse({
          error: { detail: 'A brand with this name or slug already exists.' },
          status: 409,
        }),
      ),
    ).toBe('A brand with this name or slug already exists.');
  });
});
