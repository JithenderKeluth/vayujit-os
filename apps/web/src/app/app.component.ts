import { ChangeDetectionStrategy, Component, effect, inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from './auth/auth.service';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { BrandService } from './brands/brand.service';

@Component({
  selector: 'app-root',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  readonly auth = inject(AuthService);
  readonly brands = inject(BrandService);
  private readonly router = inject(Router);
  readonly navigation = [
    ['Dashboard', '/dashboard'],
    ['Brands', '/brands'],
    ['Products', '/products'],
    ['AI Content', '/ai'],
    ['Publishing', '/publishing'],
    ['Workflows', '/workflows'],
    ['Approvals', '/approvals'],
    ['Execution History', '/execution-history'],
    ['Settings', '/settings'],
  ] as const;
  constructor() {
    effect(() => {
      if (this.auth.user()) void this.brands.loadActive();
      else this.brands.activeBrand.set(null);
    });
  }
  async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/login');
  }
}
