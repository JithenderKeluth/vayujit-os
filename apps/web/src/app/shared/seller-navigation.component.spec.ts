import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

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
  it('does not mark My Research as the current page within Business Agent', async () => {
    TestBed.inject(Router).resetConfig([{ path: 'intelligence/business-agent', component: SellerNavigationComponent }]);
    await TestBed.inject(Router).navigateByUrl('/intelligence/business-agent');
    await fixture.whenStable(); fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('a[href="/intelligence/business-agent"]')?.getAttribute('aria-current')).toBe('page');
    expect(root.querySelector('a[href="/intelligence"]')?.hasAttribute('aria-current')).toBe(false);
  });
});
