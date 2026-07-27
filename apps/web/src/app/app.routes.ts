import { Routes } from '@angular/router';

import { PlaceholderPageComponent } from './placeholder-page.component';
import { AuthPageComponent } from './auth/auth-page.component';
import { authGuard, guestGuard } from './auth/auth.guards';

const placeholder = (title: string) => ({
  component: PlaceholderPageComponent,
  data: { title },
});

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  { path: 'setup', component: AuthPageComponent, canActivate: [guestGuard] },
  { path: 'login', component: AuthPageComponent, canActivate: [guestGuard] },
  { path: 'dashboard', ...placeholder('Dashboard'), canActivate: [authGuard] },
  {
    path: 'brands',
    loadComponent: () =>
      import('./brands/brand-list.component').then((module) => module.BrandListComponent),
    canActivate: [authGuard],
  },
  {
    path: 'brands/new',
    loadComponent: () =>
      import('./brands/brand-form.component').then((module) => module.BrandFormComponent),
    canActivate: [authGuard],
  },
  {
    path: 'brands/:id/edit',
    loadComponent: () =>
      import('./brands/brand-form.component').then((module) => module.BrandFormComponent),
    canActivate: [authGuard],
  },
  {
    path: 'brands/:id',
    loadComponent: () =>
      import('./brands/brand-details.component').then((module) => module.BrandDetailsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'products',
    loadComponent: () =>
      import('./products/product-list.component').then((module) => module.ProductListComponent),
    canActivate: [authGuard],
  },
  {
    path: 'products/new',
    loadComponent: () =>
      import('./products/product-form.component').then((module) => module.ProductFormComponent),
    canActivate: [authGuard],
  },
  {
    path: 'products/:id/edit',
    loadComponent: () =>
      import('./products/product-form.component').then((module) => module.ProductFormComponent),
    canActivate: [authGuard],
  },
  {
    path: 'products/:id',
    loadComponent: () =>
      import('./products/product-details.component').then(
        (module) => module.ProductDetailsComponent,
      ),
    canActivate: [authGuard],
  },
  { path: 'workflows', ...placeholder('Workflows'), canActivate: [authGuard] },
  { path: 'approvals', ...placeholder('Approvals'), canActivate: [authGuard] },
  { path: 'execution-history', ...placeholder('Execution History'), canActivate: [authGuard] },
  { path: 'settings', ...placeholder('Settings'), canActivate: [authGuard] },
  { path: '**', redirectTo: 'dashboard' },
];
