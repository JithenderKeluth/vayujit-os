import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { AIHistoryComponent } from './ai-history.component';
import { AIUsageComponent } from './ai-usage.component';
import { AIService } from './ai.service';

const ai = {
  history: vi.fn(),
  usage: vi.fn(),
  usageHistory: vi.fn(),
  studioUsage: vi.fn(),
  usageExport: vi.fn(),
};

describe('AI history and usage acceptance', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    ai.history.mockResolvedValue({
      items: [
        {
          generation_id: 'g1',
          request_status: 'queued',
          artifact_status: null,
          created_at: '2026-01-01',
        },
        {
          generation_id: 'g2',
          request_status: 'retry_wait',
          artifact_status: 'rejected',
          created_at: '2026-01-02',
        },
        {
          generation_id: 'g3',
          request_status: 'failed',
          artifact_status: 'rejected',
          created_at: '2026-01-03',
        },
        {
          generation_id: 'g4',
          request_status: 'completed',
          artifact_status: 'approved',
          created_at: '2026-01-04',
        },
      ],
      page: 1,
      page_size: 20,
      total: 4,
      pages: 1,
    });
    ai.usage.mockResolvedValue({
      requests: 4,
      successful_generations: 1,
      failed_generations: 1,
      retries: 1,
      total_tokens: 0,
      input_tokens: 0,
      output_tokens: 0,
      estimated_cost: null,
      cost_currency: 'USD',
    });
    ai.usageHistory.mockResolvedValue({ items: [] });
    ai.studioUsage.mockResolvedValue({});
  });

  it('renders durable generation history states and safe failures', async () => {
    await TestBed.configureTestingModule({
      imports: [AIHistoryComponent],
      providers: [provideRouter([]), { provide: AIService, useValue: ai }],
    }).compileComponents();
    const fixture = TestBed.createComponent(AIHistoryComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('retry_wait');
    expect(fixture.nativeElement.textContent).toContain('approved');
    expect(ai.history).toHaveBeenCalled();
  });

  it('renders usage counters and explicitly marks cost as unavailable', async () => {
    await TestBed.configureTestingModule({
      imports: [AIUsageComponent],
      providers: [provideRouter([]), { provide: AIService, useValue: ai }],
    }).compileComponents();
    const fixture = TestBed.createComponent(AIUsageComponent);
    fixture.detectChanges();
    await fixture.componentInstance.load();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Successful / failed');
    expect(fixture.nativeElement.textContent).toContain('Cost unavailable');
    expect(fixture.nativeElement.textContent).toContain('Retries');
  });
});
