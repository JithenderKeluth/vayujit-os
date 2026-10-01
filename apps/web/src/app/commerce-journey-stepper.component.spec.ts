import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { CommerceJourneyStepperComponent } from './commerce-journey-stepper.component';

describe('CommerceJourneyStepperComponent', () => {
  it('presents actionable and blocked journey states with business labels', async () => {
    await TestBed.configureTestingModule({
      imports: [CommerceJourneyStepperComponent],
      providers: [provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(CommerceJourneyStepperComponent);
    fixture.componentInstance.stages = [
      { key: 'RESEARCH', label: 'Research', status: 'IN_PROGRESS', route: '/research' },
      { key: 'SOURCE', label: 'Source', status: 'BLOCKED', route: '/source' },
      { key: 'VERIFY', label: 'Verify', status: 'NEEDS_REVIEW', route: '/verify' },
    ];
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[data-status="IN_PROGRESS"]')?.textContent).toContain(
      'In progress',
    );
    expect(element.querySelector('[data-status="BLOCKED"]')?.textContent).toContain('Blocked');
    expect(element.querySelector('[data-status="NEEDS_REVIEW"]')?.textContent).toContain(
      'Needs review',
    );
    expect(element.querySelector('.current')).toBeTruthy();
    expect(element.querySelector('.blocked')).toBeTruthy();
    expect(element.querySelector('.review')).toBeTruthy();
  });
});
