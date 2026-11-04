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

  it('prepares exact Video lineage without creating a legacy text post or publication', async () => {
    const { component, http } = create();
    flushLoad(http);
    Object.assign(component.draft, {
      brandId: 'brand',
      productId: 'product',
      videoId: 'video',
      metadataId: 'artifact',
      metadataVersion: 2,
      accountId: 'account',
      platform: 'youtube',
      format: 'youtube_video',
    });
    component.accounts.set([
      {
        id: 'account',
        platform: 'youtube',
        display_name: 'Synthetic',
        remote_account_id: 'qa-account',
        enabled: true,
        validation_status: 'valid',
        capabilities: {},
        credential_configured: false,
      },
    ]);
    component.videos.set([
      {
        id: 'video',
        product_id: 'product',
        video_type: 'youtube_video',
        status: 'succeeded',
        output_status: 'approved',
      },
    ]);
    const pending = component.previewPost();
    const preview = http.expectOne((r) => r.url.endsWith('/ai/video/channels/preview'));
    expect(preview.request.body).toEqual(
      expect.objectContaining({
        video_generation_id: 'video',
        metadata_artifact_id: 'artifact',
        metadata_artifact_version: 2,
        target_id: 'account',
      }),
    );
    http.expectNone((r) => r.method === 'POST' && r.url.endsWith('/social/posts'));
    preview.flush({
      compatibility: 'ready',
      fingerprint: 'a'.repeat(64),
      video_output_id: 'output',
      video_version: 3,
    });
    await Promise.resolve();
    await Promise.resolve();
    http
      .expectOne((r) => r.url.endsWith('/ai/video/channels/prepare'))
      .flush({ id: 'handoff', fingerprint: 'a'.repeat(64) });
    await pending;
    expect(component.videoPreparation()?.preview['video_output_id']).toBe('output');
    component.draft.metadataVersion = 99;
    await component.confirmVideoDraft();
    expect(component.videoPreparation()).toBeNull();
    http.expectNone((r) => r.url.includes('/confirm'));
    expect(component.composeError()).toContain('stale');
    http.verify();
  });
  it('does not substitute a Video from another Product', async () => {
    const { component, http } = create();
    flushLoad(http);
    Object.assign(component.draft, {
      brandId: 'brand',
      productId: 'product',
      videoId: 'video',
      metadataId: 'artifact',
      accountId: 'account',
      platform: 'youtube',
      format: 'youtube_video',
    });
    component.accounts.set([
      {
        id: 'account',
        platform: 'youtube',
        display_name: 'Synthetic',
        remote_account_id: 'qa-account',
        enabled: true,
        validation_status: 'valid',
        capabilities: {},
        credential_configured: false,
      },
    ]);
    component.videos.set([
      { id: 'video', product_id: 'different-product', video_type: 'youtube_video' },
    ]);
    await component.previewPost();
    expect(component.composeError()).toContain('matching this Product');
    http.expectNone((r) => r.method === 'POST');
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
  it('image-only prerequisites never require a Video and reject disabled accounts', () => {
    const { component, http } = create();
    flushLoad(http);
    component.imageDraft = {
      brandId: 'brand',
      productId: 'product',
      artifactId: 'artifact',
      version: 2,
      mediaId: 'media',
      accountId: 'account',
      caption: 'Synthetic draft',
    };
    component.accounts.set([
      {
        id: 'account',
        platform: 'facebook',
        display_name: 'Synthetic',
        remote_account_id: 'qa',
        enabled: true,
        validation_status: 'valid',
        capabilities: { supported_content_types: ['facebook_post'] },
        credential_configured: false,
      },
    ]);
    expect(component.imageDraftReady()).toBe(true);
    expect(component.draft.videoId).toBe('');
    component.accounts.update((rows) => rows.map((row) => ({ ...row, enabled: false })));
    expect(component.imageDraftReady()).toBe(false);
    http.verify();
  });
  it('image draft caption changes invalidate the preview without approving or publishing', async () => {
    const { component, http } = create();
    flushLoad(http);
    component.detail.set({
      id: 'post',
      platform: 'facebook',
      content_type: 'facebook_post',
      lifecycle_status: 'draft',
      content_artifact_id: 'artifact',
      content_artifact_version: 1,
      media_ids: ['media'],
      caption: 'old',
      title: null,
      remote_publication_id: null,
      scheduled_at_utc: null,
    });
    component.imageCaption = 'new';
    const pending = component.saveImageCaption();
    const request = http.expectOne(
      (r) => r.method === 'PATCH' && r.url.endsWith('/social/posts/post'),
    );
    expect(request.request.body).toEqual({ caption: 'new' });
    request.flush({ ...component.detail(), caption: 'new', preview_fingerprint: null });
    await pending;
    expect(component.preview()).toBeNull();
    expect(component.message()).toContain('stale');
    http.expectNone((r) => r.method === 'POST');
    http.verify();
  });
  it('requires HUMAN confirmation, sends the exact fingerprint, and recovers safely from stale approval', async () => {
    const { component, http } = create();
    flushLoad(http);
    component.detail.set({
      id: 'post',
      platform: 'facebook',
      content_type: 'facebook_post',
      lifecycle_status: 'draft',
      content_artifact_id: 'artifact',
      content_artifact_version: 2,
      media_ids: ['media'],
      caption: 'exact',
      title: null,
      remote_publication_id: null,
      scheduled_at_utc: null,
    });
    component.imageCaption = 'exact';
    component.preview.set({
      post_id: 'post',
      platform: 'facebook',
      account: {} as never,
      format: 'facebook_post',
      caption: 'exact',
      title: null,
      description: null,
      media_ids: ['media'],
      hashtags: [],
      cta: null,
      schedule: {},
      readiness: { ready: true },
      fingerprint: 'a'.repeat(64),
    });
    await component.approveImageDraft();
    http.expectNone((r) => r.method === 'POST');
    component.imageHumanConfirmed = true;
    const pending = component.approveImageDraft();
    const approval = http.expectOne((r) => r.url.endsWith('/social/posts/post/approve'));
    expect(approval.request.body).toEqual({ confirm: true, preview_fingerprint: 'a'.repeat(64) });
    approval.flush({ detail: 'stale' }, { status: 409, statusText: 'Conflict' });
    await pending;
    expect(component.detail()?.lifecycle_status).toBe('draft');
    expect(component.preview()).toBeNull();
    expect(component.imageHumanConfirmed).toBe(false);
    expect(component.composeError()).toContain('rejected safely');
    http.expectNone((r) => r.url.includes('publish') || r.url.includes('schedule'));
    http.verify();
  });
});
