import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { OperationsService } from './operations.service';

describe('OperationsService', () => {
  let service: OperationsService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(OperationsService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('loads a Brand-scoped Dashboard without unbounded browser aggregation', async () => {
    const result = service.dashboard('brand-1');
    const request = http.expectOne(
      (value) =>
        value.url.endsWith('/dashboard/summary') && value.params.get('brand_id') === 'brand-1',
    );
    expect(request.request.withCredentials).toBe(true);
    request.flush({ metrics: { total_brands: 1 }, activity: [] });
    expect((await result).metrics.total_brands).toBe(1);
  });

  it('passes bounded Approval filters and pagination', async () => {
    const result = service.approvals({
      status: 'pending_review',
      brand_id: 'b1',
      search: 'title',
      page: 2,
    });
    const request = http.expectOne(
      (value) =>
        value.url.endsWith('/approvals') &&
        value.params.get('status') === 'pending_review' &&
        value.params.get('brand_id') === 'b1' &&
        value.params.get('search') === 'title' &&
        value.params.get('page') === '2',
    );
    request.flush({ items: [], page: 2, page_size: 25, total: 0, pages: 0 });
    expect((await result).page).toBe(2);
  });

  it('requests safe filtered CSV as a Blob', async () => {
    const result = service.exportHistory({ category: 'Workflow' });
    const request = http.expectOne(
      (value) =>
        value.url.endsWith('/operations/history/export') &&
        value.params.get('category') === 'Workflow',
    );
    expect(request.request.responseType).toBe('blob');
    request.flush(new Blob(['safe']));
    expect((await result).size).toBeGreaterThan(0);
  });

  it('uses exact settings write and session revocation endpoints', async () => {
    const profile = service.updateProfile('Owner');
    const profileRequest = http.expectOne('http://127.0.0.1:8000/api/v1/settings/profile');
    expect(profileRequest.request.method).toBe('PATCH');
    profileRequest.flush({ profile: { full_name: 'Owner' }, preferences: {} });
    expect((await profile).profile.full_name).toBe('Owner');
    const revoke = service.revoke('others');
    const revokeRequest = http.expectOne(
      'http://127.0.0.1:8000/api/v1/settings/sessions/revoke-others',
    );
    expect(revokeRequest.request.method).toBe('POST');
    revokeRequest.flush(null);
    await revoke;
  });
});
