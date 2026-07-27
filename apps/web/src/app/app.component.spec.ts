import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { AppComponent } from './app.component';
import { AuthService } from './auth/auth.service';

describe('AppComponent', () => {
  it('renders the application navigation', async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [provideRouter([])],
    }).compileComponents();

    const fixture = TestBed.createComponent(AppComponent);
    TestBed.inject(AuthService).user.set({
      id: 'owner-id',
      fullName: 'Local Owner',
      email: 'owner@example.com',
      role: 'owner',
    });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('VAYUJIT OS');
    expect(fixture.nativeElement.textContent).toContain('Execution History');
  });
});
