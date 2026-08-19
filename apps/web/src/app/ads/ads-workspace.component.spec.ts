/* eslint-disable @typescript-eslint/no-unsafe-return */
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
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
    expect(fixture.nativeElement.textContent).toContain(
      'Live Meta Ads and Google Ads are not validated',
    );
    http.verify();
  });
});
