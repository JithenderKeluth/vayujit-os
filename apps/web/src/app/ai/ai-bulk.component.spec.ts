import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { ProductService } from '../products/product.service';
import { AIBulkComponent } from './ai-bulk.component';
import { AIService } from './ai.service';

const ai = {
  studioBulkList: vi.fn().mockResolvedValue([]),
  studioBulk: vi.fn().mockResolvedValue(null),
  studioBulkRetryFailed: vi.fn().mockResolvedValue({}),
  studioBulkCancel: vi.fn().mockResolvedValue({}),
  studioBulkPreview: vi.fn().mockResolvedValue({ total_outputs: 1, plan_fingerprint: 'fp' }),
  studioBulkCreate: vi.fn().mockResolvedValue(null),
};
const products = { list: vi.fn().mockResolvedValue({ items: [] }) };

describe('AIBulkComponent acceptance', () => {
  let fixture: ComponentFixture<AIBulkComponent>;
  let component: AIBulkComponent;

  beforeEach(() => {
    vi.clearAllMocks();
    ai.studioBulkList.mockResolvedValue([]);
    ai.studioBulk.mockResolvedValue(null);
    ai.studioBulkRetryFailed.mockResolvedValue({});
    ai.studioBulkCancel.mockResolvedValue({});
    products.list.mockResolvedValue({ items: [] });
    TestBed.configureTestingModule({
      imports: [AIBulkComponent],
      providers: [
        provideRouter([]),
        { provide: AIService, useValue: ai },
        { provide: ProductService, useValue: products },
      ],
    });
    fixture = TestBed.createComponent(AIBulkComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => fixture.destroy());

  it('derives retry eligibility from backend output state and preserves succeeded children', () => {
    const item = {
      id: 'bulk-1',
      outputs: [
        { id: 'failed', status: 'failed', retry_eligible: true },
        { id: 'done', status: 'succeeded', retry_eligible: false },
      ],
    } as never;
    expect(component.retryable(item)).toBeTruthy();
    component.selectOperation(item);
    expect(component.operation()?.outputs[1].retry_eligible).toBeFalsy();
  });

  it('retries failed only and selected output through the service', async () => {
    const item = { id: 'bulk-1', outputs: [] } as never;
    await component.retry(item);
    await component.retryOne(item, 'child-1');
    expect(ai.studioBulkRetryFailed).toHaveBeenNthCalledWith(1, 'bulk-1');
    expect(ai.studioBulkRetryFailed).toHaveBeenNthCalledWith(2, 'bulk-1', ['child-1']);
  });

  it('requires confirmation before cancelling remaining or one child', async () => {
    const confirm = vi.spyOn(window, 'confirm');
    confirm.mockReturnValue(false);
    const item = { id: 'bulk-1', outputs: [] } as never;
    await component.cancel(item);
    expect(ai.studioBulkCancel).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    await component.cancel(item);
    await component.cancelOne(item, 'child-1');
    expect(ai.studioBulkCancel).toHaveBeenNthCalledWith(1, 'bulk-1');
    expect(ai.studioBulkCancel).toHaveBeenNthCalledWith(2, 'bulk-1', ['child-1']);
  });

  it('surfaces safe service failures and clears busy state', async () => {
    ai.studioBulkRetryFailed.mockRejectedValue({ error: { detail: 'Safe retry refusal.' } });
    await component.retry({ id: 'bulk-1', outputs: [] } as never);
    expect(component.error()).toContain('Unable to complete the AI content request.');
    expect(component.busy()).toBeFalsy();
  });

  it('prevents duplicate retry clicks while the request is pending', async () => {
    let resolveRequest: (value: object) => void = () => undefined;
    ai.studioBulkRetryFailed.mockImplementation(
      () => new Promise((resolve) => (resolveRequest = resolve)),
    );
    const item = { id: 'bulk-1', outputs: [] } as never;
    const first = component.retry(item);
    const second = component.retry(item);
    expect(ai.studioBulkRetryFailed).toHaveBeenCalledTimes(1);
    resolveRequest({});
    await first;
    await second;
  });
});
