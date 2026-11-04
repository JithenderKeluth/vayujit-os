import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { AdsOptimizationComponent } from './ads-optimization.component';
import { AIHistoryComponent } from '../ai/ai-history.component';
import { JobsComponent } from '../publishing/jobs.component';

describe('WP7 responsive tables preserve semantics and keyboard access', () => {
  afterEach(() => vi.restoreAllMocks());

  for (const section of ['recommendations', 'rules']) {
    it(`keeps ${section} in a named keyboard-scrollable region without removing columns`, async () => {
      vi.spyOn(AdsOptimizationComponent.prototype, 'ngOnInit').mockImplementation(() => {});
      await TestBed.configureTestingModule({
        imports: [AdsOptimizationComponent],
        providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
      }).compileComponents();
      const fixture = TestBed.createComponent(AdsOptimizationComponent);
      fixture.componentInstance.loading.set(false);
      fixture.componentInstance.section.set(section);
      fixture.detectChanges();
      const element = fixture.nativeElement as HTMLElement;
      const region = element.querySelector<HTMLElement>('.table-scroll');
      expect(region?.getAttribute('role')).toBe('region');
      expect(region?.getAttribute('aria-label')).toContain(section);
      expect(region?.tabIndex).toBe(0);
      expect(region?.querySelectorAll('th[scope="col"]').length).toBe(5);
      expect(element.querySelector('h1')?.textContent).toContain('Optimization intelligence');
    });
  }

  it('preserves AI history empty text, all headers and table semantics inside the scroll region', async () => {
    vi.spyOn(AIHistoryComponent.prototype, 'ngOnInit').mockImplementation(() => {});
    await TestBed.configureTestingModule({
      imports: [AIHistoryComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    const fixture = TestBed.createComponent(AIHistoryComponent);
    fixture.detectChanges();
    const region = (fixture.nativeElement as HTMLElement).querySelector<HTMLElement>(
      '.ai-table-scroll',
    );
    expect(region?.getAttribute('aria-label')).toBe('AI generation history table');
    expect(region?.tabIndex).toBe(0);
    expect(region?.querySelectorAll('th[scope="col"]').length).toBe(5);
    expect(region?.querySelector('td[colspan="5"]')?.textContent).toContain(
      'No matching generations',
    );
  });

  it('keeps all publishing job columns, truthful empty state and focusable table region', async () => {
    vi.spyOn(JobsComponent.prototype, 'ngOnInit').mockImplementation(() => {});
    await TestBed.configureTestingModule({
      imports: [JobsComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    const fixture = TestBed.createComponent(JobsComponent);
    fixture.componentInstance.loading.set(false);
    fixture.detectChanges();
    const region = (fixture.nativeElement as HTMLElement).querySelector<HTMLElement>(
      '.table-scroll',
    );
    expect(region?.getAttribute('aria-label')).toBe('Publishing jobs table');
    expect(region?.tabIndex).toBe(0);
    expect(region?.querySelectorAll('th[scope="col"]').length).toBe(8);
    expect(region?.querySelector('td[colspan="8"]')?.textContent).toContain('No jobs yet');
  });
});
