import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { SellerNavigationComponent } from './seller-navigation.component';

describe('SellerNavigationComponent', () => {
  let fixture: ComponentFixture<SellerNavigationComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SellerNavigationComponent],
      providers: [provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(SellerNavigationComponent);
    fixture.detectChanges();
  });

  it('renders a single accessible seller navigation with progressive disclosure', () => {
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('nav[aria-label="Primary navigation"]')).not.toBeNull();
    expect(root.querySelector('a[href="/dashboard"]')?.textContent).toContain('Dashboard');
    expect(root.querySelector('a[href="/intelligence/business-agent"]')).not.toBeNull();
    expect(root.querySelector('details.advanced-nav')).not.toBeNull();
    expect(root.querySelector('details.advanced-nav')?.hasAttribute('open')).toBe(false);
  });

  it('keeps route groups discoverable without exposing advanced links as primary actions', () => {
    const root = fixture.nativeElement as HTMLElement;
    const advanced = root.querySelector('details.advanced-nav') as HTMLDetailsElement;
    expect(advanced.querySelector('a[href="/intelligence/sourcing-economics"]')).not.toBeNull();
    expect(
      root.querySelector('a[href="/intelligence/sourcing-economics"]')?.closest('details'),
    ).toBe(advanced);
  });
});
