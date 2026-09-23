import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { SupplierJourneyNavComponent } from './supplier-journey-nav.component';

describe('SupplierJourneyNavComponent', () => {
  it('keeps the sourcing journey visible and marks the current step', () => {
    TestBed.configureTestingModule({
      imports: [SupplierJourneyNavComponent],
      providers: [provideRouter([])],
    });
    const fixture = TestBed.createComponent(SupplierJourneyNavComponent);
    fixture.componentRef.setInput('current', 'verify');
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('nav[aria-label="Supplier sourcing journey"]')).not.toBeNull();
    expect(root.textContent).toContain('Find suppliers');
    expect(root.textContent).toContain('Sourcing scenarios');
    expect(root.querySelector('[aria-current="step"]')?.textContent).toContain('Verify');
    expect(root.textContent).toContain('no supplier is selected or contacted automatically');
  });
});
