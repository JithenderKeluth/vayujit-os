import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { CommerceJourneyNavComponent } from './commerce-journey-nav.component';

@Component({
  standalone: true,
  imports: [CommerceJourneyNavComponent],
  template: '<app-commerce-journey-nav current="content" />',
})
class HostComponent {}

describe('CommerceJourneyNavComponent', () => {
  let fixture: ComponentFixture<HostComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HostComponent],
      providers: [provideRouter([])],
    });
    fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
  });

  it('exposes the governed commerce and creation route sequence', () => {
    const nav = (fixture.nativeElement as HTMLElement).querySelector('nav');
    if (!nav) throw new Error('Commerce journey navigation was not rendered');
    expect(nav.getAttribute('aria-label')).toBe('Commerce and creation journey');
    expect(nav.textContent).toContain('Product');
    expect(nav.textContent).toContain('Review / approval');
    expect(nav.textContent).toContain('Publishing');
    expect(nav.querySelector('[aria-current="step"]')?.textContent).toContain('Content');
    expect(nav.textContent).toContain('governed publishing');
  });
});
