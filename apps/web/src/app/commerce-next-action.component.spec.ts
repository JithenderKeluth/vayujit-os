import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { CommerceNextActionComponent } from './commerce-next-action.component';

describe('CommerceNextActionComponent accessibility', () => {
  it('uses a named task region, not a complementary landmark nested in main', async () => {
    await TestBed.configureTestingModule({
      imports: [CommerceNextActionComponent],
      providers: [provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(CommerceNextActionComponent);
    fixture.componentInstance.action = {
      code: 'REVIEW',
      title: 'Review evidence',
      detail: 'No supplier has been approved.',
      route: '/research',
      human_controlled: true,
    };
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('aside')).toBeNull();
    expect(element.querySelector('section[aria-label="Next best action"]')).not.toBeNull();
    expect(element.querySelector('a')?.textContent).toContain('Open workspace');
  });
});
