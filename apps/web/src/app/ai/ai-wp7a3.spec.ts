import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { vi } from 'vitest';
import { AIStudioComponent } from './ai-studio.component';
import { AIArtifactComponent } from './ai-artifact.component';
import { AIService } from './ai.service';
import { OperationsService } from '../operations/operations.service';
import { WorkflowService } from '../workflows/workflow.service';

describe('WP7A3 persisted content review', () => {
  const generation = {
    id: 'gen',
    status: 'failed',
    product_ids: ['product'],
    outputs: [
      { status: 'failed', job_id: 'a' },
      { status: 'failed', job_id: 'b' },
    ],
  };
  let ai: {
    studioGeneration: ReturnType<typeof vi.fn>;
    studioArtifacts: ReturnType<typeof vi.fn>;
    studioRetry: ReturnType<typeof vi.fn>;
    studioGenerate: ReturnType<typeof vi.fn>;
    studioEdit: ReturnType<typeof vi.fn>;
  };
  let router: { navigate: ReturnType<typeof vi.fn> };
  beforeEach(() => {
    ai = {
      studioGeneration: vi.fn().mockResolvedValue(generation),
      studioArtifacts: vi.fn().mockResolvedValue([]),
      studioRetry: vi.fn().mockResolvedValue({}),
      studioGenerate: vi.fn().mockResolvedValue(generation),
      studioEdit: vi.fn().mockResolvedValue({ id: 'revision', status: 'pending_review' }),
    };
    router = { navigate: vi.fn().mockResolvedValue(true) };
    TestBed.configureTestingModule({
      providers: [
        { provide: AIService, useValue: ai },
        { provide: Router, useValue: router },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { queryParamMap: { get: () => null }, paramMap: { get: () => 'source' } },
          },
        },
        {
          provide: OperationsService,
          useValue: {
            approval: vi.fn().mockResolvedValue({ artifact: { id: 'revision' }, versions: [] }),
          },
        },
        { provide: WorkflowService, useValue: {} },
      ],
    });
  });
  it('retries every failed output by its exact persisted job, not the first generation job repeatedly', async () => {
    const c = TestBed.runInInjectionContext(() => new AIStudioComponent());
    c.generation.set(generation as never);
    await c.retryGeneration();
    expect(ai.studioRetry.mock.calls).toEqual([
      ['gen', 'a'],
      ['gen', 'b'],
    ]);
    expect(ai.studioGeneration).toHaveBeenCalledWith('gen');
    expect(c.busy()).toBe(false);
  });
  it('refreshes authoritative status and never invents successful outputs', async () => {
    const c = TestBed.runInInjectionContext(() => new AIStudioComponent());
    c.generation.set(generation as never);
    await c.loadArtifacts();
    expect(c.generation()?.status).toBe('failed');
    expect(c.artifacts()).toEqual([]);
  });
  it('does not enqueue duplicate actions while busy or without a product', async () => {
    const c = TestBed.runInInjectionContext(() => new AIStudioComponent());
    await c.generate();
    c.productId.set('product');
    c.busy.set(true);
    await c.generate();
    expect(ai.studioGenerate).not.toHaveBeenCalled();
  });
  it('follows the new revision ID and retains the source unchanged', async () => {
    const c = TestBed.runInInjectionContext(() => new AIArtifactComponent());
    const source = {
      id: 'source',
      content: {
        product_title: 'Original',
        long_description: 'Original',
        key_features: ['Original'],
      },
    };
    c.artifact.set(source as never);
    c.draftTitle = 'Revised';
    c.draftDescription = 'Revised';
    c.draftBullets = 'One';
    await c.saveEdit();
    expect(router.navigate).toHaveBeenCalledWith(['/ai/artifacts', 'revision'], {
      queryParamsHandling: 'preserve',
    });
    expect(source.content.product_title).toBe('Original');
  });
  it('does not navigate on a stale or approved-source rejection', async () => {
    const c = TestBed.runInInjectionContext(() => new AIArtifactComponent());
    c.artifact.set({ id: 'source', content: {} } as never);
    ai.studioEdit.mockRejectedValue({ status: 409 });
    await c.saveEdit();
    expect(router.navigate).not.toHaveBeenCalled();
    expect(c.error()).toBeTruthy();
    expect(c.busy()).toBe(false);
  });
  it('does not submit a legacy content bundle to the incompatible Studio translation authority', async () => {
    const c = TestBed.runInInjectionContext(() => new AIArtifactComponent());
    await c.translate({ content_type: 'product_content' } as never);
    expect(ai.studioGenerate).not.toHaveBeenCalled();
    expect(c.error()).toContain('legacy bundles are unsupported');
  });
});
