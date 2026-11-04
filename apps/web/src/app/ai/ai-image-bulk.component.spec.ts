import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { vi } from 'vitest';
import { AIImageBulkComponent } from './ai-image-bulk.component';
import { AIService } from './ai.service';
import { ProductService } from '../products/product.service';

describe('saved bulk image operation', () => {
  let ai: { imageBulkStatus: ReturnType<typeof vi.fn>; imageBulkCreate: ReturnType<typeof vi.fn> };
  beforeEach(() => {
    ai = {
      imageBulkStatus: vi.fn().mockResolvedValue({ id: 'op', status: 'completed' }),
      imageBulkCreate: vi.fn(),
    };
    TestBed.configureTestingModule({
      providers: [
        { provide: AIService, useValue: ai },
        { provide: ProductService, useValue: { list: vi.fn().mockResolvedValue({ items: [] }) } },
        { provide: Router, useValue: { navigate: vi.fn().mockResolvedValue(true) } },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: { get: () => 'op' } } } },
      ],
    });
  });
  it('restores exact operation on reload through the canonical owner-scoped API', async () => {
    const c = TestBed.runInInjectionContext(() => new AIImageBulkComponent());
    c.ngOnInit();
    await Promise.resolve();
    await Promise.resolve();
    expect(ai.imageBulkStatus).toHaveBeenCalledWith('op');
    expect(c.status()?.status).toBe('completed');
  });
  it('clears unavailable context without substituting another operation', async () => {
    const c = TestBed.runInInjectionContext(() => new AIImageBulkComponent());
    c.status.set({ id: 'old', status: 'completed' } as never);
    ai.imageBulkStatus.mockRejectedValue({ status: 404 });
    await c.refreshStatus('missing');
    expect(c.status()).toBeNull();
    expect(c.error()).toContain('unavailable');
  });
  it('blocks duplicate enqueue while a request is outstanding', async () => {
    const c = TestBed.runInInjectionContext(() => new AIImageBulkComponent());
    c.busy.set(true);
    await c.queue();
    expect(ai.imageBulkCreate).not.toHaveBeenCalled();
  });
  it('does not enqueue a preview with canonical prerequisite blockers', async () => {
    const c = TestBed.runInInjectionContext(() => new AIImageBulkComponent());
    c.previewData.set({ blockers: ['Select a source Media asset.'] } as never);
    await c.queue();
    expect(ai.imageBulkCreate).not.toHaveBeenCalled();
  });
  it('exposes a keyboard-focusable horizontal output review region', async () => {
    ai.imageBulkStatus.mockResolvedValue({
      id: 'op',
      status: 'completed',
      outputs: [],
      total_outputs: 1,
      progress_percentage: 100,
    });
    const fixture = TestBed.createComponent(AIImageBulkComponent);
    await fixture.whenStable();
    fixture.componentInstance.status.set({
      id: 'op',
      status: 'failed',
      outputs: [],
      total_outputs: 1,
      progress_percentage: 100,
    } as never);
    fixture.detectChanges();
    const region = (fixture.nativeElement as HTMLElement).querySelector<HTMLElement>(
      '[aria-label="Bulk image output review queue"]',
    );
    expect(region?.getAttribute('tabindex')).toBe('0');
    expect(region?.querySelector('table')).not.toBeNull();
  });
});
