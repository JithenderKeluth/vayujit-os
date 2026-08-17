import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

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

  it('navigates all fourteen wizard steps and preserves bounds', () => {
    const { component } = create();
    expect(component.stepLabel()).toBe('Product');
    for (let index = 0; index < 20; index += 1) component.nextStep();
    expect(component.step()).toBe(14);
    expect(component.stepLabel()).toBe('Queue');
    for (let index = 0; index < 20; index += 1) component.previousStep();
    expect(component.step()).toBe(1);
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
