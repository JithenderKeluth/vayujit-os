import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import type { DashboardResponse } from '@vayujit/shared';
import { vi } from 'vitest';

import { BrandService } from '../brands/brand.service';
import { DashboardComponent } from './dashboard.component';
import { OperationsService } from './operations.service';

const metrics = {
  total_brands: 0,
  total_products: 0,
  active_products: 0,
  pending_approvals: 0,
  approved_artifacts: 0,
  active_destinations: 0,
  successful_executions: 0,
  failed_executions: 0,
  waiting_workflows: 0,
  completed_workflows: 0,
  failed_workflows: 0,
  retryable_failures: 0,
};

function response(overrides: Partial<typeof metrics> = {}): DashboardResponse {
  return { metrics: { ...metrics, ...overrides }, activity: [] };
}

describe('DashboardComponent', () => {
  const activeBrand = signal(null);
  const brands = {
    activeBrand,
    list: vi.fn().mockResolvedValue({ items: [] }),
    loadActive: vi.fn().mockResolvedValue(null),
  };
  const operations = { dashboard: vi.fn() };

  async function create(data: DashboardResponse | Error) {
    operations.dashboard.mockReset();
    if (data instanceof Error) operations.dashboard.mockRejectedValue(data);
    else operations.dashboard.mockResolvedValue(data);
    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideRouter([]),
        { provide: BrandService, useValue: brands },
        { provide: OperationsService, useValue: operations },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(DashboardComponent);
    fixture.detectChanges();
    await fixture.whenStable();
    await new Promise((resolve) => setTimeout(resolve, 10));
    fixture.detectChanges();
    return fixture;
  }

  it('provides a governed Ask path, quick starts, and a derived first-use state', async () => {
    const fixture = await create(response());
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('h1')?.textContent).toContain(
      'What would you like to accomplish?',
    );
    expect(element.querySelector('a[href="/intelligence/business-agent"]')?.textContent).toContain(
      'Open Business Agent',
    );
    expect(element.textContent).toContain('Start your first VAYUJIT research journey');
    expect(element.querySelector('a[href="/intelligence/product-opportunities"]')).toBeTruthy();
    expect(element.querySelector('a[href="/intelligence/sourcing"]')).toBeTruthy();
    expect(element.querySelector('a[href="/campaigns"]')).toBeTruthy();
    expect(element.querySelector('a[href="/operations"]')).toBeTruthy();
  });

  it('shows authoritative attention statuses and metric workspace links', async () => {
    const fixture = await create(
      response({
        total_products: 4,
        active_products: 3,
        pending_approvals: 2,
        failed_executions: 1,
        waiting_workflows: 1,
        retryable_failures: 1,
      }),
    );
    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Approvals awaiting review');
    expect(element.textContent).toContain('Failed publishing executions');
    expect(element.textContent).toContain('Workflows waiting for approval');
    expect(element.textContent).toContain('Retryable publishing failures');
    expect(element.textContent).not.toContain('Recommended');
    expect(element.querySelector('a[href="/approvals"]')).toBeTruthy();
    expect(element.querySelector('a[href="/execution-history"]')).toBeTruthy();
    expect(element.querySelector('a[href="/workflows"]')).toBeTruthy();
    expect(element.querySelector('[data-status="PENDING_REVIEW"]')).toBeTruthy();
    expect(element.querySelector('[data-status="WAITING_FOR_APPROVAL"]')).toBeTruthy();
    expect(element.querySelector('a[href="/products"]')?.textContent).toContain('Open workspace');
  });

  it('renders the shared retryable error state without exposing backend details', async () => {
    const fixture = await create(new Error('backend detail should stay hidden'));
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[role="alert"]')?.textContent).toContain(
      'Some operational data could not be loaded.',
    );
    expect(element.querySelector('button')?.textContent).toContain('Try again');
    expect(element.textContent).not.toContain('backend detail should stay hidden');
  });
});
