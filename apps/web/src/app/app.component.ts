import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { AuthService } from './auth/auth.service';
import { Router, RouterLink, RouterOutlet } from '@angular/router';
import { BrandService } from './brands/brand.service';
import { OperationsService } from './operations/operations.service';
import { BreadcrumbService } from './shared/breadcrumb.service';
import { BreadcrumbsComponent } from './shared/breadcrumbs.component';
import { SellerNavigationComponent } from './shared/seller-navigation.component';

@Component({
  selector: 'app-root',
  imports: [RouterLink, RouterOutlet, BreadcrumbsComponent, SellerNavigationComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  readonly auth = inject(AuthService);
  readonly brands = inject(BrandService);
  private readonly router = inject(Router);
  private readonly operations = inject(OperationsService);
  readonly breadcrumbs = inject(BreadcrumbService);
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
  focusMainContent(event: MouseEvent): void {
    event.preventDefault();
    const target = document.getElementById('main-content');
    target?.focus({ preventScroll: false });
  }
  closeMobileMenu(event: Event, menu: HTMLDetailsElement): void {
    event.preventDefault();
    menu.open = false;
    menu.querySelector('summary')?.focus();
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
