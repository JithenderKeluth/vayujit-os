import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { TrendIntelligenceWorkspaceComponent } from './trend-intelligence-workspace.component';

describe('TrendIntelligenceWorkspaceComponent', () => {
  let fixture: ComponentFixture<TrendIntelligenceWorkspaceComponent>;
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TrendIntelligenceWorkspaceComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(TrendIntelligenceWorkspaceComponent);
    fixture.detectChanges();
  });
  it('renders an evidence-first workspace', () => {
    expect(fixture.nativeElement.textContent).toContain('Trend Intelligence');
    expect(fixture.nativeElement.textContent).toContain('Evidence-first');
  });
});
