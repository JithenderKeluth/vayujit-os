import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { SocialWorkspaceComponent } from './social-workspace.component';

describe('SocialWorkspaceComponent', () => {
  function create() {
    TestBed.configureTestingModule({
      imports: [SocialWorkspaceComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(SocialWorkspaceComponent);
    const http = TestBed.inject(HttpTestingController);
    return { fixture, component: fixture.componentInstance, http };
  }

  function flushLoad(http: HttpTestingController) {
    http.expectOne((request) => request.url.endsWith('/social/accounts')).flush([]);
    http.expectOne((request) => request.url.endsWith('/social/posts')).flush([]);
    http
      .expectOne((request) => request.url.endsWith('/social/platforms'))
      .flush([
        { key: 'youtube', name: 'YouTube', formats: ['youtube_video', 'youtube_short'] },
        { key: 'instagram', name: 'Instagram', formats: ['instagram_reel', 'instagram_story'] },
      ]);
    http.expectOne((request) => request.url.endsWith('/social/recovery')).flush([]);
    http.expectOne((request) => request.url.endsWith('/ai/video/generations')).flush([]);
    http
      .expectOne((request) => request.url.endsWith('/social/analytics/summary'))
      .flush({
        publications: 0,
        published: 0,
        failed: 0,
        scheduled: 0,
        metrics: {},
        synthetic: true,
      });
  }

  it('derives platform formats from server capability data', () => {
    const { component, http } = create();
    flushLoad(http);
    component.platforms.set([
      { key: 'youtube', name: 'YouTube', formats: ['youtube_video', 'youtube_short'] },
      { key: 'instagram', name: 'Instagram', formats: ['instagram_reel', 'instagram_story'] },
    ]);
    component.draft.platform = 'youtube';
    component.syncFormat();
    expect(component.compatibleFormats()).toEqual(['youtube_video', 'youtube_short']);
    component.draft.platform = 'instagram';
    component.syncFormat();
    expect(component.compatibleFormats()).toEqual(['instagram_reel', 'instagram_story']);
    http.verify();
  });

  it('requires exact identities and an enabled validated account before preview', () => {
    const { component, http } = create();
    flushLoad(http);
    component.draft.brandId = 'brand';
    component.draft.productId = 'product';
    component.draft.videoId = 'video';
    component.draft.metadataId = 'artifact';
    component.draft.accountId = 'account';
    component.draft.format = 'youtube_video';
    component.accounts.set([
      {
        id: 'account',
        platform: 'youtube',
        display_name: 'Owner YouTube',
        remote_account_id: 'remote',
        enabled: true,
        validation_status: 'valid',
        capabilities: {},
        credential_configured: true,
      },
    ]);
    expect(component.ready()).toBe(true);
    component.draft.accountId = '';
    expect(component.ready()).toBe(false);
    http.verify();
  });

  it('renders semantic loading and empty-state messaging', () => {
    const { fixture, http } = create();
    flushLoad(http);
    fixture.detectChanges();
    expect(
      fixture.nativeElement.querySelector('nav[aria-label="Social workspace"]'),
    ).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('No Video posts yet');
    http.verify();
  });
});
