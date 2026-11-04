import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { AIVideoComponent } from './ai-video.component';

describe('AIVideoComponent', () => {
  function create() {
    TestBed.configureTestingModule({
      imports: [AIVideoComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(AIVideoComponent);
    const http = TestBed.inject(HttpTestingController);
    http.match(() => true).forEach((request) => request.flush([]));
    fixture.detectChanges();
    return { fixture, component: fixture.componentInstance, http };
  }

  it('exposes one routed section and a named, accurate progressbar', () => {
    const { fixture, component } = create();
    expect(fixture.nativeElement.querySelector('main')).toBeNull();
    const root = fixture.nativeElement as HTMLElement;
    const bar = root.querySelector('[role="progressbar"]')!;
    expect(bar.getAttribute('aria-label')).toBe('Generate workflow progress');
    expect(bar.getAttribute('aria-valuenow')).toBe('1');
    component.nextStep();
    fixture.detectChanges();
    expect(bar.getAttribute('aria-valuenow')).toBe('2');
    expect(bar.getAttribute('aria-valuemax')).toBe('14');
  });

  it('navigates all fourteen wizard steps and preserves bounds', () => {
    const { component } = create();
    expect(component.stepLabel()).toBe('Product');
    for (let index = 0; index < 20; index += 1) component.nextStep();
    expect(component.step()).toBe(14);
    expect(component.stepLabel()).toBe('Queue');
    for (let index = 0; index < 20; index += 1) component.previousStep();
    expect(component.step()).toBe(1);
  });
  it('retries only an eligible failure with pinned state and suppresses double clicks', async () => {
    const { component, http } = create();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    component.selectedVideo.set({ id: 'generation', status: 'failed' });
    component.recovery.set({
      status: 'failed',
      failure_code: 'ai.video.provider_unavailable',
      attempt_count: 3,
      eligible_actions: ['retry_generation'],
    });
    component.error.set('old failure');
    const pending = component.retryVideo();
    await component.retryVideo();
    const request = http.expectOne((r) => r.url.endsWith('/generation/recovery'));
    expect(request.request.body).toEqual({
      action: 'retry_generation',
      expected_status: 'failed',
      expected_failure_code: 'ai.video.provider_unavailable',
      idempotency_key: 'video-retry:generation:3',
    });
    request.flush({ id: 'generation', status: 'queued' });
    await Promise.resolve();
    await Promise.resolve();
    http
      .match(() => true)
      .forEach((r) =>
        r.flush(
          r.request.url.endsWith('/recovery') ? { status: 'queued', eligible_actions: [] } : [],
        ),
      );
    await pending;
    expect(component.error()).toBe('');
    expect(component.selectedVideo()?.['status']).toBe('queued');
    expect(component.canRetryVideo()).toBe(false);
    expect(component.retrying()).toBe(false);
    vi.restoreAllMocks();
    http.verify();
  });

  it('does not retry an unreviewed or ineligible Video state', async () => {
    const { component, http } = create();
    component.selectedVideo.set({ id: 'generation', status: 'succeeded' });
    component.recovery.set({ status: 'succeeded', eligible_actions: ['retry_generation'] });
    await component.retryVideo();
    http.expectNone((r) => r.method === 'POST');
    http.match((r) => r.method === 'GET').forEach((r) => r.flush([]));
    http.verify();
  });
  it('clears unavailable video results and recovers a previous failure only on a new canonical load', async () => {
    const { component, http } = create();
    component.videos.set([{ id: 'old' }]);
    const failed = component.load();
    http
      .match(() => true)
      .forEach((r) =>
        r.request.url.endsWith('/generations')
          ? r.flush({}, { status: 503, statusText: 'Unavailable' })
          : r.flush([]),
      );
    await failed;
    expect(component.videos()).toEqual([]);
    expect(component.error()).toContain('unavailable');
    const recovered = component.load();
    http.match(() => true).forEach((r) => r.flush([]));
    await recovered;
    expect(component.error()).toBe('');
    expect(component.loading()).toBe(false);
  });

  it('supports keyboard-safe storyboard scene operations', () => {
    const { component } = create();
    component.editableScenes.set([{ stable_key: 'one', scene_order: 1, scene_text: 'A' }]);
    component.addScene();
    component.duplicateScene(0);
    component.moveScene(1, 1);
    component.removeScene(1);
    expect(component.editableScenes().map((scene) => scene['scene_order'])).toEqual([1, 2]);
    expect(component.sceneReady(component.editableScenes()[0])).toBe(true);
  });

  it('has one named caption input and a supported Quick actions group', () => {
    const { fixture } = create();
    expect(
      fixture.nativeElement.querySelectorAll('textarea[aria-label="Caption text"]').length,
    ).toBe(1);
    expect(fixture.nativeElement.querySelector('.quick-actions').getAttribute('role')).toBe(
      'group',
    );
    const root = fixture.nativeElement as HTMLElement;
    const table = root.querySelector<HTMLTableElement>(
      '[aria-label="Video generation history"] table',
    )!;
    expect(table.querySelectorAll('th[scope="col"]').length).toBe(8);
    expect(table.querySelector('td[colspan]')!.getAttribute('colspan')).toBe('8');
  });

  it('uses the entered caption, never placeholder content, and refuses empty input', async () => {
    const { component, http } = create();
    component.selectVideo({ id: 'video-caption' });
    http.match(() => true).forEach((r) => r.flush([]));
    component.captionLocale = 'en-IN';
    await component.addCaption();
    http.expectNone((r) => r.method === 'POST');
    component.captionText = '  Seller-entered caption  ';
    const save = component.addCaption();
    const request = http.expectOne((r) => r.method === 'POST');
    expect(request.request.body.caption_text).toBe('Seller-entered caption');
    expect(request.request.body.timing[0].text).toBe('Seller-entered caption');
    request.flush({});
    await Promise.resolve();
    http.match(() => true).forEach((r) => r.flush([]));
    await save;
  });

  it('identifies same-version storyboards by their exact board and product context', () => {
    const { fixture, component } = create();
    component.storyboards.set([
      { id: 'board-a', product_id: 'product-a', version: 1, state: 'draft', scenes: [] },
      { id: 'board-b', product_id: 'product-b', version: 1, state: 'draft', scenes: [] },
    ]);
    fixture.detectChanges();
    const cards = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll('#storyboards .cards .card'),
    ];
    expect(cards[0].textContent).toContain('board-a');
    expect(cards[0].textContent).toContain('product-a');
    expect(cards[0].textContent).not.toContain('product-b');
    expect(cards[1].textContent).toContain('board-b');
    expect(cards[1].textContent).toContain('product-b');
  });

  it('clears stale caption feedback on a new attempt, preserving server rejection and explicit review', async () => {
    const { component, http } = create();
    component.selectVideo({ id: 'caption-retry' });
    http.match(() => true).forEach((r) => r.flush([]));
    component.captionLocale = 'en-IN';
    component.captionText = 'Seller-entered caption';
    component.message.set('Old success');
    const rejected = component.addCaption();
    expect(component.message()).toBe('');
    http.expectOne((r) => r.method === 'POST').flush({}, { status: 422, statusText: 'Invalid' });
    await rejected;
    expect(component.error()).toBe('Caption track could not be created safely.');
    const retried = component.addCaption();
    expect(component.error()).toBe('');
    http.expectOne((r) => r.method === 'POST').flush({ approval_state: 'pending_review' });
    await Promise.resolve();
    http.match(() => true).forEach((r) => r.flush([]));
    await retried;
    expect(component.error()).toBe('');
    expect(component.message()).toBe('Caption track created for review.');
  });

  it('requires owner context before queueing and exposes safe review state', () => {
    const { component } = create();
    expect(component.canQueue()).toBe(false);
    component.brandId = 'brand-id';
    component.productId = 'product-id';
    expect(component.canQueue()).toBe(true);
    component.selectVideo({ id: 'video-id', output_media_id: 'media-id' });
    expect(component.selectedVideo()?.['id']).toBe('video-id');
  });

  it('projects recovery, history, usage, and diagnostics without leaking paths', async () => {
    const { component, http } = create();
    component.selectVideo({ id: 'video-1', status: 'failed', size_bytes: 2048 });
    http.expectOne((request) => request.url.endsWith('/generations/video-1/captions')).flush([]);
    const history = component.loadHistory();
    http
      .expectOne((request) => request.url.endsWith('/generations/video-1/history'))
      .flush([
        { state: 'queued' },
        { state: 'retry_wait' },
        { state: 'failed' },
        { state: 'succeeded' },
      ]);
    await history;
    const recovery = component.loadRecovery();
    http
      .expectOne((request) => request.url.endsWith('/generations/video-1/recovery'))
      .flush({
        safe_message: 'Retry is available.',
        retryable: true,
        eligible_actions: ['retry'],
        correlation_id: 'corr-1',
        local_path: 'C:\\private\\secret',
      });
    await recovery;
    expect(component.history().length).toBe(4);
    expect(component.recovery()?.['retryable']).toBe(true);
    expect(component.diagnosticEntries({ generated_bytes: 2048, local_path: 'hidden' })).toEqual([
      ['generated_bytes', '2048'],
    ]);
    component.videos.set([{ status: 'failed', size_bytes: 2048 }]);
    expect(component.totalBytes()).toBe('2,048 bytes');
    expect(component.metrics().find((item) => item.label === 'Failed')?.value).toBe(1);
  });
});
