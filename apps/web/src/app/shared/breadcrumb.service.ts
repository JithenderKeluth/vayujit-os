import { Injectable, inject, signal } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';

import type { BreadcrumbItem } from './ux-foundation.types';

const LABELS: Record<string, string> = {
  ads: 'Ads',
  ai: 'AI Studio',
  brands: 'Brands',
  campaigns: 'Campaigns',
  calendar: 'Calendar',
  competitors: 'Competitors',
  dashboard: 'Dashboard',
  intelligence: 'Intelligence',
  marketplaces: 'Marketplaces',
  media: 'Media',
  operations: 'Operations',
  products: 'Products',
  publishing: 'Publishing',
  reviews: 'Reviews',
  settings: 'Settings',
  social: 'Social',
  sourcing: 'Sourcing',
  trends: 'Trend Intelligence',
  workflows: 'Workflows',
};

@Injectable({ providedIn: 'root' })
export class BreadcrumbService {
  private readonly router = inject(Router);
  readonly items = signal<BreadcrumbItem[]>(this.resolve(this.router.url));

  constructor() {
    this.router.events
      .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
      .subscribe((event) => this.items.set(this.resolve(event.urlAfterRedirects)));
  }

  private resolve(url: string): BreadcrumbItem[] {
    const path = url.split('?')[0].split('#')[0];
    const segments = path.split('/').filter(Boolean);
    if (!segments.length) return [];

    const items: BreadcrumbItem[] = [{ label: 'Home', url: '/dashboard' }];
    let accumulated = '';
    segments.forEach((segment, index) => {
      accumulated += `/${segment}`;
      const isLast = index === segments.length - 1;
      items.push({
        label: LABELS[segment] || this.humanize(segment),
        ...(isLast ? {} : { url: accumulated }),
      });
    });
    return items;
  }

  private humanize(segment: string): string {
    return decodeURIComponent(segment)
      .replace(/[-_]+/g, ' ')
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }
}
