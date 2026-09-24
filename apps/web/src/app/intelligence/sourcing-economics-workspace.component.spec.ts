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
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Sourcing economic inputs');
    expect(text).toContain('Final landed-cost calculations come later');
    expect(text).toContain('UNKNOWN is unavailable; it is never displayed as zero');
    expect(fixture.nativeElement.querySelector('[aria-label="Breadcrumb"]')).not.toBeNull();
    expect(fixture.nativeElement.innerHTML).not.toContain('<script');
  });
});
