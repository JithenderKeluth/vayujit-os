import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { SourcingScenariosComponent } from './sourcing-scenarios.component';

describe('SourcingScenariosComponent', () => {
  it('renders the human-controlled decision-support boundary', () => {
    TestBed.configureTestingModule({
      imports: [SourcingScenariosComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(SourcingScenariosComponent);
    fixture.componentInstance.ngOnInit = () => undefined;
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Sourcing Scenarios');
    expect(text).toContain('No supplier contact, orders, or payments');
    expect(text).toContain('Create analysis context');
  });

  it('keeps approval disabled for incomplete analysis', () => {
    TestBed.configureTestingModule({
      imports: [SourcingScenariosComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(SourcingScenariosComponent);
    const component = fixture.componentInstance;
    component.ngOnInit = () => undefined;
    component.reason = 'reviewed';
    component.confirmed = true;
    expect(component.canApprove()).toBe(false);
  });

  it('submits generation with an explicit request key and renders evidenced labels', async () => {
    TestBed.configureTestingModule({
      imports: [SourcingScenariosComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    const fixture = TestBed.createComponent(SourcingScenariosComponent);
    const component = fixture.componentInstance;
    component.ngOnInit = () => undefined;
    component.contextId.set('context-1');
    component.addAllocation();
    component.allocations[0].supplier_id = 'supplier-1';
    component.allocations[0].due_diligence_id = 'diligence-1';
    component.allocations[0].unit_price = '10';
    component.allocations[0].assumption_reason = 'Verified fixture';
    const http = TestBed.inject(HttpTestingController);
    const pending = component.generateScenarios();
    const request = http.expectOne(component.base + '/contexts/context-1/generate');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.idempotency_key).toBeTruthy();
    expect(request.request.body.basis.idempotency_key).toBeTruthy();
    request.flush({
      generated: [{ id: 'scenario-1', name: 'Baseline A', labels: ['LOWEST_COST'] }],
      explanation: 'Human review required.',
    });
    await Promise.resolve();
    http.expectOne(component.base + '/contexts/context-1/comparison').flush({ scenarios: [] });
    await pending;
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('LOWEST_COST');
    expect(fixture.nativeElement.textContent).toContain('1 evidenced baseline scenarios generated');
    http.expectOne(component.base + '/contexts').flush([]);
    await Promise.resolve();
    http.expectOne('/api/v1/intelligence/supplier-shortlisting/contexts').flush([]);
    await Promise.resolve();
    http.expectOne('/api/v1/intelligence/supplier-due-diligence/contexts').flush([]);
    await Promise.resolve();
    http.verify();
  });
});
