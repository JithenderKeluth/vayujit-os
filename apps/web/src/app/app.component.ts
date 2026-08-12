import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from './auth/auth.service';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { BrandService } from './brands/brand.service';
import { OperationsService } from './operations/operations.service';

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
  private readonly operations = inject(OperationsService);
  readonly navigation = [
    ['Dashboard', '/dashboard'],
    ['Brands', '/brands'],
    ['Products', '/products'],
    ['Campaigns', '/campaigns'],
    ['Calendar', '/calendar'],
    ['Social', '/social'],
    ['AI Studio', '/ai/studio'],
    ['AI Images', '/ai/images'],
    ['Brand Voices', '/ai/brand-voices'],
    ['Presets', '/ai/presets'],
    ['Media', '/media'],
    ['Publishing', '/publishing'],
    ['Marketplace', '/marketplaces'],
    ['Schedules', '/publishing/schedules'],
    ['Jobs', '/publishing/jobs'],
    ['Workflows', '/workflows'],
    ['Approvals', '/approvals'],
    ['Execution History', '/execution-history'],
    ['Operations', '/operations'],
    ['Settings', '/settings'],
  ] as const;
  readonly maintenance = signal(false);
  constructor() {
    effect(() => {
      if (this.auth.user()) {
        void this.restoreBrandContext();
        void this.loadMaintenance();
      } else this.brands.activeBrand.set(null);
    });
  }
  private async loadMaintenance(): Promise<void> {
    try {
      this.maintenance.set((await this.operations.maintenance()).enabled);
    } catch {
      this.maintenance.set(false);
    }
  }
  async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/login');
  }
  private async restoreBrandContext(): Promise<void> {
    const active = await this.brands.loadActive();
    if (active) return;
    try {
      const id = (await this.operations.settings()).preferences.default_brand_id;
      if (id) await this.brands.activate(id);
    } catch {
      // An unavailable preference must never prevent application startup.
    }
  }
}
