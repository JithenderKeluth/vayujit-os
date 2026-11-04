import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { vi } from 'vitest';
import { FinancialWorkspaceComponent } from '../marketplaces/financial-workspace.component';
import {
  MarketplaceService,
  FinancialSummary,
  UnifiedOrder,
} from '../marketplaces/marketplace.service';
import { ActionCenterComponent } from './action-center.component';
import { ActionCenterService } from './action-center.service';
import { AppComponent } from '../app.component';
import { AuthService } from '../auth/auth.service';
import { BrandService } from '../brands/brand.service';
import { OperationsService } from './operations.service';
import { UnifiedOrdersComponent } from '../marketplaces/unified-orders.component';

const summary = {
  currency: 'INR',
  gross_sales: '200.25',
  net_sales: '200.25',
  fees: '20.05',
  known_direct_costs: 'UNKNOWN',
  contribution: 'UNKNOWN',
  estimated_profit: null,
  missing_inputs: ['product_cost_evidence'],
  evidence_status: 'partial',
  basis: 'financial event effective_at',
  calculation_version: 'v1',
  synthetic_provider: true,
  order_count: 1,
  event_count: 2,
} as FinancialSummary;
function financeApi() {
  return Object.fromEntries(
    [
      'financialSummary',
      'financialProfitability',
      'financialFees',
      'financialSettlements',
      'financialAlerts',
      'financialRevenueTrends',
      'financialMarketplaceComparison',
      'financialRefundImpact',
      'financialBusinessAgent',
    ].map((name) => [
      name,
      vi.fn().mockResolvedValue(name === 'financialSummary' ? summary : null),
    ]),
  );
}

describe('WP5 financial projection scope and recovery', () => {
  async function create() {
    const api = financeApi();
    await TestBed.configureTestingModule({
      imports: [FinancialWorkspaceComponent],
      providers: [provideRouter([]), { provide: MarketplaceService, useValue: api }],
    }).compileComponents();
    const fixture = TestBed.createComponent(FinancialWorkspaceComponent);
    await fixture.whenStable();
    fixture.detectChanges();
    return { fixture, api, c: fixture.componentInstance };
  }
  it('labels mutable projection history, synthetic provenance and revenue separately from profit', async () => {
    const { fixture } = await create();
    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('not an accounting ledger');
    expect(text).toContain('not immutable accounting history');
    expect(text).toContain('Synthetic fixture');
    expect(text).toContain('₹200.25');
    expect(text).toContain('UNKNOWN');
    expect(
      fixture.nativeElement.querySelector('label[for=financial-marketplace]')?.textContent,
    ).toBe('Marketplace');
  });
  it('clears old figures when a new filter fails, without a successful empty-state claim', async () => {
    const { fixture, api, c } = await create();
    api['financialSummary'].mockRejectedValue(new Error('safe seam'));
    c.marketplace.set('amazon');
    await c.load();
    fixture.detectChanges();
    expect(c.summary()).toBeNull();
    expect(c.loadedAt()).toBe('');
    expect(fixture.nativeElement.textContent).toContain('Financial evidence is unavailable');
    expect(fixture.nativeElement.textContent).not.toContain('Financial workspace is ready');
    expect(fixture.nativeElement.querySelector('[aria-label="Sales summary"]')).toBeNull();
  });
  it('does not let an older response overwrite a newer period', async () => {
    const { api, c } = await create();
    let older!: (v: FinancialSummary) => void;
    api['financialSummary'].mockReturnValueOnce(new Promise((r) => (older = r)));
    const first = c.load();
    c.marketplace.set('amazon');
    api['financialSummary'].mockResolvedValue({ ...summary, gross_sales: '9.00' });
    await c.load();
    older(summary);
    await first;
    expect(c.summary()?.gross_sales).toBe('9.00');
  });
  it('rejects invalid periods without reading or showing prior figures', async () => {
    const { api, c } = await create();
    api['financialSummary'].mockClear();
    c.dateFrom.set('2026-11-02');
    c.dateTo.set('2026-11-01');
    await c.load();
    expect(c.summary()).toBeNull();
    expect(c.error()).toContain('Date from');
    expect(api['financialSummary']).not.toHaveBeenCalled();
  });
});

describe('WP5 Action Center bounded local actions', () => {
  async function create() {
    const api = {
      load: vi.fn().mockResolvedValue({ signals: [], total: 0, briefing: null, policy: null }),
      scan: vi.fn(),
      transition: vi.fn(),
      detail: vi.fn(),
    };
    await TestBed.configureTestingModule({
      imports: [ActionCenterComponent],
      providers: [provideRouter([]), { provide: ActionCenterService, useValue: api }],
    }).compileComponents();
    const f = TestBed.createComponent(ActionCenterComponent);
    await f.whenStable();
    return { c: f.componentInstance, api };
  }
  it('handles scan failures visibly and does not claim success', async () => {
    const { c, api } = await create();
    api.scan.mockRejectedValue(new Error('not for display'));
    await c.refreshScan();
    expect(c.error()).toContain('not confirmed');
    expect(c.notice()).toBe('');
    expect(c.busy()).toBe(false);
  });
  it('blocks a repeated pending action and only reports confirmed completion', async () => {
    const { c, api } = await create();
    let done!: (v: unknown) => void;
    api.scan.mockReturnValue(new Promise((r) => (done = r)));
    const first = c.refreshScan();
    await c.refreshScan();
    expect(api.scan).toHaveBeenCalledTimes(1);
    expect(c.busy()).toBe(true);
    done({});
    await first;
    expect(c.notice()).toContain('rescanned');
  });
  it('does not turn a rejected stale transition into a successful decision', async () => {
    const { c, api } = await create();
    api.transition.mockRejectedValue({ status: 409 });
    await c.resolve({ id: 'a' } as never);
    expect(c.error()).toContain('Evidence may have changed');
    expect(c.notice()).toBe('');
  });
  it('uses the current detail response rather than stale tile evidence', async () => {
    const { c, api } = await create();
    const stale = { id: 'a', status: 'NEW' },
      fresh = { id: 'a', status: 'STALE' };
    c.data.set([stale as never]);
    api.detail.mockResolvedValue({ signal: fresh, history: [] });
    await c.inspect(stale as never);
    expect(c.selected()?.status).toBe('STALE');
    expect(c.data()[0].status).toBe('STALE');
  });
});

describe('WP5 provenance presentation', () => {
  it('makes stored unit rounding explicit without recalculating canonical line totals', async () => {
    await TestBed.configureTestingModule({
      imports: [UnifiedOrdersComponent],
      providers: [
        provideRouter([]),
        {
          provide: MarketplaceService,
          useValue: {
            unifiedOrders: vi.fn().mockResolvedValue([]),
            unifiedInsights: vi.fn().mockResolvedValue(null),
          },
        },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(UnifiedOrdersComponent);
    await fixture.whenStable();
    fixture.componentInstance.selectedOrder.set({
      id: 'a',
      remote_order_id: 'Synthetic price',
      fake_provider: true,
      currency: 'INR',
      lines: [
        {
          id: 'line',
          product_id: null,
          marketplace_sku: 'QA',
          title: 'Synthetic line',
          quantity: 2,
          unit_price: '100.13',
          total_price: '200.25',
        },
      ],
    } as UnifiedOrder);
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('Stored unit price (rounded)');
    expect(text).toContain('must not be reconstructed');
    expect(text).toContain('₹100.13');
    expect(text).toContain('₹200.25');
  });
  it('does not describe an order-read error as a successful empty history', async () => {
    await TestBed.configureTestingModule({
      imports: [UnifiedOrdersComponent],
      providers: [
        provideRouter([]),
        {
          provide: MarketplaceService,
          useValue: {
            unifiedOrders: vi.fn().mockRejectedValue(new Error('safe seam')),
            unifiedInsights: vi.fn().mockResolvedValue(null),
          },
        },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(UnifiedOrdersComponent);
    await fixture.whenStable();
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.textContent).toContain('Orders are unavailable');
    expect(element.textContent).not.toContain('No matching local orders');
  });
  it('never calls absent order provenance real/provider verified', () => {
    expect(UnifiedOrdersComponent.prototype.sourceLabel({} as UnifiedOrder)).toBe(
      'Provenance UNKNOWN',
    );
    expect(
      UnifiedOrdersComponent.prototype.sourceLabel({ fake_provider: true } as UnifiedOrder),
    ).toContain('Synthetic');
    expect(
      UnifiedOrdersComponent.prototype.sourceLabel({
        provenance_status: 'REPORTED',
      } as UnifiedOrder),
    ).toContain('not independently verified');
  });
});

@Component({ template: '<h1>Operational destination</h1>' })
class Destination {}
describe('WP5 mobile navigation completion', () => {
  it('closes the menu after successful navigation and focuses main content', async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideRouter([
          { path: 'dashboard', component: Destination },
          { path: 'operations/action-center', component: Destination },
        ]),
        {
          provide: AuthService,
          useValue: { user: signal({ fullName: 'Synthetic', email: 'qa@example.com' }) },
        },
        {
          provide: BrandService,
          useValue: {
            activeBrand: signal(null),
            loadActive: vi.fn().mockResolvedValue({ id: 'a' }),
          },
        },
        {
          provide: OperationsService,
          useValue: { maintenance: vi.fn().mockResolvedValue({ enabled: false }) },
        },
      ],
    }).compileComponents();
    const f = TestBed.createComponent(AppComponent);
    f.detectChanges();
    await f.whenStable();
    const menu = f.nativeElement.querySelector('details.mobile-menu') as HTMLDetailsElement;
    menu.open = true;
    await TestBed.inject(Router).navigateByUrl('/operations/action-center');
    await f.whenStable();
    expect(menu.open).toBe(false);
    expect(document.activeElement?.id).toBe('main-content');
  });
});
