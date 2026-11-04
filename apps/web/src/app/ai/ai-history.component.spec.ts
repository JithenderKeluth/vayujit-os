import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { AIHistoryComponent } from './ai-history.component';
import { AIService } from './ai.service';

describe('AI history accessibility remediation', () => {
  function create() {
    const history = vi.fn().mockResolvedValue({ items: [], pages: 1 });
    TestBed.configureTestingModule({
      imports: [AIHistoryComponent],
      providers: [provideRouter([]), { provide: AIService, useValue: { history } }],
    });
    const fixture = TestBed.createComponent(AIHistoryComponent);
    return { fixture, history };
  }
  it('associates every status/date filter with a visible label and keeps the action heading', async () => {
    const { fixture } = create();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    for (const control of root.querySelectorAll<HTMLInputElement | HTMLSelectElement>(
      'input,select',
    ))
      expect(control.labels?.[0].textContent?.trim()).toBeTruthy();
    expect(
      root.querySelector<HTMLInputElement>('input[name="dateFrom"]')?.labels?.[0]?.textContent,
    ).toContain('Date from');
    expect(
      root.querySelector<HTMLSelectElement>('select[name="artifactStatus"]')?.labels?.[0]
        ?.textContent,
    ).toContain('Review status');
    expect(root.querySelector('th:last-child')?.textContent).toBe('Actions');
  });
  it('announces load errors without changing filter/query behavior', async () => {
    const { fixture, history } = create();
    history.mockRejectedValue(new Error('Offline'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]')?.textContent.trim()).toBeTruthy();
    expect(history).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }));
  });
});
