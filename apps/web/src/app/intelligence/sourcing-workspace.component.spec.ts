import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { IntelligenceService } from './intelligence.service';
import { SourcingWorkspaceComponent } from './sourcing-workspace.component';

describe('SourcingWorkspaceComponent', () => {
  it('keeps unknown seller economics blank and blocks incomplete calculation', async () => {
    const service: Partial<IntelligenceService> = {
      sourcingOverview: vi.fn().mockResolvedValue({}),
      sourcingRequirements: vi.fn().mockResolvedValue({ items: [] }),
    };
    await TestBed.configureTestingModule({
      imports: [SourcingWorkspaceComponent],
      providers: [provideRouter([]), { provide: IntelligenceService, useValue: service }],
    }).compileComponents();

    const fixture = TestBed.createComponent(SourcingWorkspaceComponent);
    const component = fixture.componentInstance;
    expect(component.scenario.inputs.unit_supplier_price).toBeNull();
    expect(component.scenario.inputs.freight).toBeNull();
    expect(component.scenario.inputs.selling_price).toBeNull();
    expect(component.quote.unit_price).toBeNull();
    await component.createQuote();
    expect(component.error()).toContain('Enter a supplier unit price');
    await component.calculate();
    expect(component.error()).toContain('Enter supplier price, freight, and selling price');
    expect(service.sourcingRequirements).toHaveBeenCalled();
  });
});
