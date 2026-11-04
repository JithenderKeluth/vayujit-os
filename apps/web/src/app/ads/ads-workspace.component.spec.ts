/* eslint-disable @typescript-eslint/no-unsafe-return */
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { AdsWorkspaceComponent } from './ads-workspace.component';

describe('AdsWorkspaceComponent', () => {
  function create() {
    TestBed.configureTestingModule({
      imports: [AdsWorkspaceComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(AdsWorkspaceComponent);
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/v1/ads/overview').flush({
      accounts: [],
      campaigns: [],
      active_campaigns: 0,
      paused: 0,
      failed: 0,
      metrics: {},
      attention_items: [],
      synthetic: true,
    });
    http.expectOne('/api/v1/ads/capabilities').flush({
      meta: {
        objectives: ['awareness'],
        bidding_strategies: ['lowest_cost'],
        creative_types: ['content', 'image', 'video'],
      },
      google: {
        objectives: ['traffic'],
        bidding_strategies: ['maximize_clicks'],
        creative_types: ['content', 'image', 'video'],
      },
    });
    return { fixture, component: fixture.componentInstance, http };
  }

  it('keeps provider choices and wizard objectives server-derived', () => {
    const { component, http } = create();
    component.capabilities = {
      google: {
        objectives: ['traffic'],
        bidding_strategies: ['maximize_clicks'],
        creative_types: ['content'],
      },
    };
    component.campaignDraft.provider = 'google';
    expect(component.providerCapability()?.objectives).toEqual(['traffic']);
    component.syncProvider();
    expect(component.campaignDraft.objective).toBe('traffic');
    expect(component.wizardSteps).toHaveLength(12);
    http.verify();
  });

  it('filters campaigns by bounded search, provider, and state', () => {
    const { component, http } = create();
    component.campaigns = [
      { id: 'one', name: 'Spring Meta', provider: 'meta', state: 'active' },
      { id: 'two', name: 'Google Draft', provider: 'google', state: 'draft' },
    ];
    component.campaignSearch = 'spring';
    component.applyCampaignFilters();
    expect(component.filteredCampaigns.map((item) => item.id)).toEqual(['one']);
    component.campaignSearch = '';
    component.campaignProvider = 'google';
    component.campaignState = 'draft';
    component.applyCampaignFilters();
    expect(component.filteredCampaigns.map((item) => item.id)).toEqual(['two']);
    http.verify();
  });

  it('renders a local boundary and accessible navigation', () => {
    const { fixture, component, http } = create();
    component.overview = {
      accounts: [],
      campaigns: [],
      active_campaigns: 0,
      paused: 0,
      failed: 0,
      metrics: {},
      attention_items: [
        'Live Meta Ads and Google Ads are not validated in this local environment.',
      ],
    };
    component.loading.set(false);
    fixture.detectChanges();
    expect(
      fixture.nativeElement.querySelector('nav[aria-label="Ads workspace navigation"]'),
    ).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('LOCAL SYNTHETIC');
    expect(fixture.nativeElement.textContent).toContain('Meesho Ads is not supported');
    expect(fixture.nativeElement.textContent).toContain(
      'Live Meta Ads and Google Ads are not validated',
    );
    http.verify();
  });

  it('confirms the exact previewed payload and canonical fingerprint with one stable intention', async () => {
    const { component, http } = create();
    component.campaignDraft.name = 'Synthetic campaign';
    const preview = component.previewCampaign();
    const request = http.expectOne('/api/v1/ads/campaigns/preview');
    const payload: unknown = request.request.body;
    request.flush({ fingerprint: 'a'.repeat(64) });
    await preview;
    component.confirmChecked = true;
    const first = component.confirmCampaign();
    await component.confirmCampaign(); // in-flight duplicate cannot submit again
    const confirmation = http.expectOne('/api/v1/ads/campaigns/confirm');
    const intention = confirmation.request.body as {
      campaign: unknown;
      preview_fingerprint: string;
    };
    expect(intention.campaign).toEqual(payload);
    expect(intention.preview_fingerprint).toBe('a'.repeat(64));
    confirmation.flush({}, { status: 503, statusText: 'Unavailable' });
    await first;
    const replay = component.confirmCampaign();
    const retried = http.expectOne('/api/v1/ads/campaigns/confirm');
    expect(retried.request.body).toEqual(intention);
    retried.flush({}, { status: 503, statusText: 'Unavailable' });
    await replay;
    http.verify();
  });

  it('requires a new preview and HUMAN review after a material input change', async () => {
    const { component, http } = create();
    const preview = component.previewCampaign();
    http.expectOne('/api/v1/ads/campaigns/preview').flush({ fingerprint: 'b'.repeat(64) });
    await preview;
    component.confirmChecked = true;
    component.campaignDraft.budget.amount = '99.25';
    await component.confirmCampaign();
    http.expectNone('/api/v1/ads/campaigns/confirm');
    expect(component.preview()).toBeNull();
    expect(component.confirmChecked).toBe(false);
    expect(component.error()).toContain('inputs changed');
    http.verify();
  });

  it('uses observed failure identity for recovery rather than replaying an older failure forever', async () => {
    const { component, http } = create();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const pending = component.runRecovery(
      {
        entity_id: 'campaign',
        entity_type: 'campaign',
        failure_code: 'ads.connector_unavailable',
        correlation_id: 'second-failure',
      },
      'retry',
    );
    const request = http.expectOne('/api/v1/ads/recovery');
    expect(request.request.body.idempotency_key).toContain('second-failure');
    request.flush({}, { status: 503, statusText: 'Unavailable' });
    await pending;
    vi.restoreAllMocks();
    http.verify();
  });

  it('checks prospective readiness with the selected account and immutable image identity', async () => {
    const { component, http } = create();
    component.campaignDraft.account_id = 'owned-account';
    component.creativeDraft.creative_type = 'image';
    component.creativeDraft.image_output_id = 'approved-output';
    component.creativeDraft.media_id = 'matching-media';
    component.creativeDraft.media_version = 1;
    const pending = component.checkReadiness();
    const request = http.expectOne('/api/v1/ads/creatives/readiness');
    expect(request.request.body.account_id).toBe('owned-account');
    expect(request.request.body.image_output_id).toBe('approved-output');
    expect(request.request.body.image_media_id).toBe('matching-media');
    request.flush({ status: 'ready', prospective: true, approval_granted: false });
    await pending;
    http.verify();
  });

  it('includes the exact creative in preview and rejects an edited creative before confirmation', async () => {
    const { component, http } = create();
    component.creativeDraft.artifact_id = 'exact-artifact';
    component.creativeDraft.artifact_version = 2;
    const pending = component.previewCampaign();
    const request = http.expectOne('/api/v1/ads/campaigns/preview');
    expect(request.request.body.creative.artifact_id).toBe('exact-artifact');
    expect(request.request.body.creative.artifact_version).toBe(2);
    request.flush({ fingerprint: 'a'.repeat(64) });
    await pending;
    component.confirmChecked = true;
    component.creativeDraft.artifact_version = 3;
    await component.confirmCampaign();
    http.expectNone('/api/v1/ads/campaigns/confirm');
    expect(component.error()).toContain('inputs changed');
    http.verify();
  });
});
