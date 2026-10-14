import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { SourcingEconomicsWorkspaceComponent } from './sourcing-economics-workspace.component';

describe('SourcingEconomicsWorkspaceComponent', () => {
  it('renders evidence-first input guidance and keeps unknown distinct from zero', async () => {
    await TestBed.configureTestingModule({
      imports: [SourcingEconomicsWorkspaceComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(SourcingEconomicsWorkspaceComponent);
    fixture.componentInstance.context.set({
      id: 'context-1',
      status: 'ready',
      base_currency: 'USD',
      target_quantity: 1,
      quantity_unit: 'unit',
    });
    fixture.componentInstance.snapshot.set({
      id: 'snapshot-1',
      version: 1,
      fingerprint: 'fingerprint-1',
      completeness: 'complete',
    });
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Sourcing economic inputs');
    expect(text).toContain('calculate a reproducible known-cost subtotal');
    expect(text).toContain('UNKNOWN is unavailable; it is never displayed as zero');
    expect(text).toContain('Freight snapshot ID (optional)');
    expect(text).toContain('no live carrier quote is fetched');
    expect(fixture.nativeElement.querySelector('[aria-label="Breadcrumb"]')).not.toBeNull();
    expect(fixture.nativeElement.innerHTML).not.toContain('<script');
  });

  it('uses a stable HUMAN decision idempotency key for the current journey context', async () => {
    await TestBed.configureTestingModule({
      imports: [SourcingEconomicsWorkspaceComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(SourcingEconomicsWorkspaceComponent);
    const component = fixture.componentInstance;
    component.journeyId = 'journey-1';
    component.opportunityId = 'opportunity-1';

    expect(component.decisionIdempotencyKey('keep_under_review')).toBe(
      'pr6c-ui-decision-journey-1-opportunity-1-KEEP_UNDER_REVIEW',
    );
    expect(component.decisionIdempotencyKey('keep_under_review')).toBe(
      component.decisionIdempotencyKey('keep_under_review'),
    );
    expect(component.decisionIdempotencyKey('proceed')).not.toBe(
      component.decisionIdempotencyKey('do_not_proceed'),
    );
  });

  it('does not present launch preparation as available while the canonical brief is blocked', async () => {
    await TestBed.configureTestingModule({
      imports: [SourcingEconomicsWorkspaceComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(SourcingEconomicsWorkspaceComponent);
    const component = fixture.componentInstance;
    component.decisionBrief.set({ decision_readiness: 'NEEDS_REVIEW' } as never);

    expect(component.decisionActionAvailable('PROCEED_TO_LAUNCH_PREPARATION')).toBe(false);
    expect(component.decisionActionAvailable('RESEARCH_FURTHER')).toBe(true);
  });
});
