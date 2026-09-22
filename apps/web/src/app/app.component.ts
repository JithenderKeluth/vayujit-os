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
  readonly navigationGroups = [
    {
      label: 'Home',
      items: [['Dashboard', '/dashboard']] as const,
    },
    {
      label: 'Discover',
      items: [
        ['Intelligence', '/intelligence'],
        ['Trend Intelligence', '/intelligence/trends'],
        ['Competitors', '/intelligence/competitors'],
        ['Reviews', '/intelligence/reviews'],
        ['Business Agent', '/intelligence/business-agent'],
        ['External Research', '/intelligence/external'],
        ['Website Intelligence', '/intelligence/websites'],
        ['Autonomous Research', '/intelligence/autonomous'],
        ['IndiaMART Discovery', '/intelligence/indiamart'],
        ['Alibaba Discovery', '/intelligence/alibaba'],
        ['TradeIndia Discovery', '/intelligence/tradeindia'],
        ['Global Sources Discovery', '/intelligence/global-sources'],
      ] as const,
    },
    {
      label: 'Source',
      items: [
        ['Sourcing', '/intelligence/sourcing'],
        ['Supplier Shortlisting', '/intelligence/supplier-shortlisting'],
        ['Cross-marketplace Suppliers', '/intelligence/cross-marketplace'],
      ] as const,
    },
    {
      label: 'Create',
      items: [
        ['AI Studio', '/ai/studio'],
        ['AI Video', '/ai/video'],
        ['AI Images', '/ai/images'],
        ['Brand Voices', '/ai/brand-voices'],
        ['Presets', '/ai/presets'],
        ['Media', '/media'],
      ] as const,
    },
    {
      label: 'Grow',
      items: [
        ['Campaigns', '/campaigns'],
        ['Ads', '/ads'],
        ['Social', '/social'],
      ] as const,
    },
    {
      label: 'Sell',
      items: [
        ['Brands', '/brands'],
        ['Products', '/products'],
        ['Marketplace', '/marketplaces'],
        ['Marketplace Video', '/marketplaces/video'],
        ['Publishing', '/publishing'],
      ] as const,
    },
    {
      label: 'Operate',
      items: [
        ['Calendar', '/calendar'],
        ['Schedules', '/publishing/schedules'],
        ['Jobs', '/publishing/jobs'],
        ['Workflows', '/workflows'],
        ['Approvals', '/approvals'],
        ['Execution History', '/execution-history'],
        ['Operations', '/operations'],
      ] as const,
    },
    {
      label: 'System',
      items: [['Settings', '/settings']] as const,
    },
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
