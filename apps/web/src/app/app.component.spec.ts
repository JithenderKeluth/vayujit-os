import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { AppComponent } from './app.component';
import { AuthService } from './auth/auth.service';

describe('AppComponent', () => {
  it('renders the application navigation', async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    const fixture = TestBed.createComponent(AppComponent);
    TestBed.inject(AuthService).user.set({
      id: 'owner-id',
      fullName: 'Local Owner',
      email: 'owner@example.com',
      role: 'owner',
    });
    fixture.detectChanges();
    TestBed.inject(HttpTestingController)
      .expectOne('http://127.0.0.1:8000/api/v1/brands/active')
      .flush(null);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('VAYUJIT OS');
    expect(fixture.nativeElement.textContent).toContain('Execution History');
  });
});
