import { provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { GrowthJourneyNavComponent } from './growth-journey-nav.component';

describe('GrowthJourneyNavComponent', () => {
  it('renders the governed growth journey with a current step', () => {
    TestBed.configureTestingModule({
      imports: [GrowthJourneyNavComponent],
      providers: [provideRouter([])],
    });
    const fixture = TestBed.createComponent(GrowthJourneyNavComponent);
    fixture.componentRef.setInput('current', 'campaigns');
    fixture.detectChanges();

    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('nav[aria-label="Growth journey"]')).not.toBeNull();
    expect(root.querySelector('[aria-current="step"]')?.textContent).toContain('Campaigns');
    expect(root.textContent).toContain('Review, approval, scheduling, and recovery');
  });
});
