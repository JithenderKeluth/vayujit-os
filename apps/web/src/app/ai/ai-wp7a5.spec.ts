import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, of } from 'rxjs';
import { describe, it, expect, vi } from 'vitest';
import { AIVideoBulkComponent } from './ai-video-bulk.component';
import { AISeoComponent } from './ai-seo.component';
import { AIService } from './ai.service';
import { CampaignVideoComponent } from '../campaigns/campaign-video.component';
import { CampaignService } from '../campaigns/campaign.service';
import { environment } from '../../environments/environment';

const id = '00000000-0000-4000-8000-000000000001';
const bulkUrl = environment.apiUrl + '/ai/video/bulk/';
const route = (query: Record<string, string> = {}) => ({
  snapshot: {
    paramMap: convertToParamMap({ id, activityId: 'exact-activity' }),
    queryParamMap: convertToParamMap(query),
  },
  queryParamMap: of(convertToParamMap(query)),
  paramMap: of(convertToParamMap({ id, activityId: 'exact-activity' })),
});
describe('WP7A5 exact canonical workflow integration', () => {
  it('does not retain a previous activity when route parameters change during a request', async () => {
    const params = new BehaviorSubject(convertToParamMap({ id, activityId: 'old' }));
    let resolveOld!: (value: unknown) => void;
    const api = {
      videoDetail: vi.fn().mockImplementation((_campaign: string, activity: string) =>
        activity === 'old'
          ? new Promise((resolve) => {
              resolveOld = resolve;
            })
          : Promise.resolve({ campaign: { name: 'New' }, activity: { id: activity } }),
      ),
    };
    TestBed.configureTestingModule({
      imports: [CampaignVideoComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { ...route(), paramMap: params } },
        { provide: CampaignService, useValue: api },
      ],
    });
    const component = TestBed.createComponent(CampaignVideoComponent).componentInstance;
    params.next(convertToParamMap({ id, activityId: 'new' }));
    await vi.waitFor(() => expect(component.selectedActivity()?.id).toBe('new'));
    resolveOld({ campaign: { name: 'Old' }, activity: { id: 'old' } });
    await Promise.resolve();
    expect(component.selectedActivity()?.id).toBe('new');
  });
  it('loads the exact campaign activity authority, not a nearby overview', async () => {
    const api = {
      videoDetail: vi.fn().mockResolvedValue({
        campaign: { name: 'Exact campaign' },
        activity: { id: 'exact-activity', name: 'Exact activity' },
      }),
      get: vi.fn(),
    };
    TestBed.configureTestingModule({
      imports: [CampaignVideoComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: route() },
        { provide: CampaignService, useValue: api },
      ],
    });
    const component = TestBed.createComponent(CampaignVideoComponent).componentInstance;
    await vi.waitFor(() => {
      expect(component.loading()).toBe(false);
    });
    expect(api.videoDetail).toHaveBeenCalledWith(id, 'exact-activity');
    expect(api.get).not.toHaveBeenCalled();
    expect(component.selectedActivity()?.id).toBe('exact-activity');
  });
  it('does not substitute another activity when exact detail fails', async () => {
    const api = { videoDetail: vi.fn().mockRejectedValue(new Error('not found')) };
    TestBed.configureTestingModule({
      imports: [CampaignVideoComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: route() },
        { provide: CampaignService, useValue: api },
      ],
    });
    const component = TestBed.createComponent(CampaignVideoComponent).componentInstance;
    await vi.waitFor(() => {
      expect(component.loading()).toBe(false);
    });
    expect(component.detail()).toBeNull();
    expect(component.activities()).toEqual([]);
    expect(component.error()).toBeTruthy();
  });
  function bulk() {
    TestBed.configureTestingModule({
      imports: [AIVideoBulkComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ActivatedRoute, useValue: route({ operation: id }) },
      ],
    });
    const component = TestBed.createComponent(AIVideoBulkComponent).componentInstance;
    const http = TestBed.inject(HttpTestingController);
    return { component, http };
  }
  it('reopens persisted identity and history without queueing new work', () => {
    const { component, http } = bulk();
    http.expectOne(bulkUrl + id).flush({ id, children: [], status: 'succeeded' });
    http.expectOne(bulkUrl + id + '/history').flush([{ action: 'created' }]);
    expect(component.operation()?.id).toBe(id);
    expect(component.history()).toHaveLength(1);
    http.expectNone((r) => r.method === 'POST');
    http.verify();
  });
  it('blocks duplicate retries and preserves backend failure reporting', () => {
    const { component, http } = bulk();
    http
      .expectOne(bulkUrl + id)
      .flush({ id, children: [{ id: 'child', status: 'failed', retryable: true }] });
    http.expectOne(bulkUrl + id + '/history').flush([]);
    component.recover('retry-failed');
    component.recover('retry-failed');
    const pending = http.expectOne(bulkUrl + id + '/retry-failed');
    pending.flush({ detail: 'stale recovery' }, { status: 409, statusText: 'Conflict' });
    expect(component.error()).toContain('stale recovery');
    expect(component.busy()).toBe(false);
    http.verify();
  });
  it('retains default deny on missing operation and nonretryable children', () => {
    const { component, http } = bulk();
    http.expectOne(bulkUrl + id).flush({}, { status: 404, statusText: 'Not Found' });
    http.expectOne(bulkUrl + id + '/history').flush([]);
    component.recover('retry-failed');
    expect(component.operation()).toBeNull();
    http.expectNone((r) => r.method === 'POST');
    http.verify();
  });
  it('saves scoped keyword metadata and reloads canonical revision lists', async () => {
    const api = {
      seoSets: vi.fn().mockResolvedValue([]),
      seoCreateKeywords: vi.fn().mockResolvedValue({ id }),
      seoUpdateSet: vi.fn(),
    };
    TestBed.configureTestingModule({
      imports: [AISeoComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: route({ product: id }) },
        { provide: AIService, useValue: api },
      ],
    });
    const component = TestBed.createComponent(AISeoComponent).componentInstance;
    component.keywordName = 'Synthetic keywords';
    component.keywordPaste = 'one\ntwo';
    await component.saveKeywords();
    expect(api.seoCreateKeywords).toHaveBeenCalledWith(
      expect.objectContaining({ product_id: id, primary: ['one'], secondary: ['two'] }),
    );
    expect(api.seoSets).toHaveBeenCalledWith('keywords');
  });
  it('updates saved tags rather than silently creating another set', async () => {
    const api = {
      seoSets: vi.fn().mockResolvedValue([]),
      seoCreateTags: vi.fn(),
      seoUpdateSet: vi.fn().mockResolvedValue({ id }),
    };
    TestBed.configureTestingModule({
      imports: [AISeoComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: route({ product: id }) },
        { provide: AIService, useValue: api },
      ],
    });
    const component = TestBed.createComponent(AISeoComponent).componentInstance;
    component.editSet('tags', {
      id,
      name: 'Saved',
      product_id: id,
      locale: 'en-IN',
      tags: ['old'],
    });
    component.tagPaste = 'new';
    await component.saveTags();
    expect(api.seoUpdateSet).toHaveBeenCalledWith(
      'tags',
      id,
      expect.objectContaining({ tags: ['new'], product_id: id }),
    );
    expect(api.seoCreateTags).not.toHaveBeenCalled();
  });
});
