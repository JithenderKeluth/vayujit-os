import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { of } from 'rxjs';
import { AdsOptimizationComponent } from './ads-optimization.component';

describe('AdsOptimizationComponent read-only preview keyboard behavior', () => {
  it('enters the dialog, contains forward/reverse Tab, closes with Escape and restores focus', async () => {
    await TestBed.configureTestingModule({
      imports: [AdsOptimizationComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { url: of([{ path: 'recommendations' }]) } },
      ],
    }).compileComponents();
    vi.spyOn(AdsOptimizationComponent.prototype, 'ngOnInit').mockImplementation(() => undefined);
    const fixture = TestBed.createComponent(AdsOptimizationComponent);
    const http = TestBed.inject(HttpTestingController);
    // Isolate focus management from the seven independent data-loading requests.
    // Actual persisted loading/authorization remains a separate browser/backend gate.
    fixture.componentInstance.section.set('recommendations');
    fixture.componentInstance.recommendations = [{ id: 'r', type: 'review_destination' }];
    fixture.componentInstance.loading.set(false);
    fixture.detectChanges();
    const trigger = (fixture.nativeElement as HTMLElement).querySelector(
      'tbody button',
    ) as HTMLButtonElement;
    expect({
      section: fixture.componentInstance.section(),
      loading: fixture.componentInstance.loading(),
      recommendations: fixture.componentInstance.recommendations.length,
    }).toEqual({ section: 'recommendations', loading: false, recommendations: 1 });
    expect(trigger, (fixture.nativeElement as HTMLElement).textContent || '').not.toBeNull();
    trigger.focus();
    trigger.click();
    http
      .expectOne('/api/v1/ads/recommendations/r/preview')
      .flush({ synthetic: true, execution: false });
    await fixture.whenStable();
    fixture.detectChanges();
    const dialog = (fixture.nativeElement as HTMLElement).querySelector(
      '[role=dialog]',
    ) as HTMLElement;
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement?.id).toBe('preview-title');
    for (const shiftKey of [false, true]) {
      const key = new KeyboardEvent('keydown', {
        key: 'Tab',
        shiftKey,
        bubbles: true,
        cancelable: true,
      });
      document.dispatchEvent(key);
      expect(key.defaultPrevented).toBe(true);
      expect(document.activeElement?.textContent).toBe('Close');
    }
    document.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }),
    );
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role=dialog]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
    const outsideTab = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true });
    fixture.componentInstance.onPreviewKeydown(outsideTab);
    expect(outsideTab.defaultPrevented).toBe(false);
    http.verify();
    vi.restoreAllMocks();
  });
});
