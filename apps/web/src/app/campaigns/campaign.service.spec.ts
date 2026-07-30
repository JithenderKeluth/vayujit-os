import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { CampaignService } from './campaign.service';

describe('CampaignService', () => {
  let service: CampaignService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CampaignService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('loads bounded calendar events with credentials', async () => {
    const result = service.calendar(
      '2026-08-01T00:00:00.000Z',
      '2026-09-01T00:00:00.000Z',
      'month',
      'campaign-1',
    );
    const request = http.expectOne(
      (candidate) =>
        candidate.url.endsWith('/campaigns/calendar') &&
        candidate.params.get('campaign_id') === 'campaign-1',
    );
    expect(request.request.withCredentials).toBe(true);
    request.flush({
      view: 'month',
      start: '2026-08-01T00:00:00.000Z',
      end: '2026-09-01T00:00:00.000Z',
      days: [],
    });
    expect((await result).view).toBe('month');
  });

  it('requires explicit confirmation for Campaign scheduling', async () => {
    const result = service.schedule('campaign-1', ['activity-1']);
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/campaigns/campaign-1/schedule');
    expect(request.request.body).toEqual({
      activity_ids: ['activity-1'],
      behavior: 'require_all_ready',
      confirm: true,
    });
    request.flush({ campaign_id: 'campaign-1', results: [] });
    expect((await result)['campaign_id']).toBe('campaign-1');
  });

  it('sends an explicit missed-activity policy on resume', async () => {
    const result = service.resume('campaign-1', 'one_catch_up');
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/campaigns/campaign-1/resume');
    expect(request.request.body.missed_activity_policy).toBe('one_catch_up');
    request.flush({ id: 'campaign-1', status: 'scheduled' });
    expect((await result).status).toBe('scheduled');
  });

  it('never places connector credentials in Campaign requests', async () => {
    const result = service.create({
      brand_id: 'brand-1',
      name: 'Launch',
      timezone_name: 'UTC',
      local_start_at: '2026-08-01T09:00',
      local_end_at: '2026-08-02T09:00',
    });
    const request = http.expectOne('http://127.0.0.1:8000/api/v1/campaigns');
    expect(JSON.stringify(request.request.body)).not.toContain('password');
    expect(JSON.stringify(request.request.body)).not.toContain('token');
    request.flush({ id: 'campaign-1', status: 'draft' });
    expect((await result).id).toBe('campaign-1');
  });
});
