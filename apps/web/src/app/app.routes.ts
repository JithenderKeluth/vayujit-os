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
  {
    path: 'ai',
    loadComponent: () => import('./ai/ai-home.component').then((module) => module.AIHomeComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/generate',
    loadComponent: () =>
      import('./ai/ai-generate.component').then((module) => module.AIGenerateComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/artifacts/:id',
    loadComponent: () =>
      import('./ai/ai-artifact.component').then((module) => module.AIArtifactComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/history',
    loadComponent: () =>
      import('./ai/ai-history.component').then((module) => module.AIHistoryComponent),
    canActivate: [authGuard],
  },
  {
    path: 'publishing',
    loadComponent: () =>
      import('./publishing/publishing-dashboard.component').then(
        (m) => m.PublishingDashboardComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/destinations',
    loadComponent: () =>
      import('./publishing/destination-list.component').then((m) => m.DestinationListComponent),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/destinations/new',
    loadComponent: () =>
      import('./publishing/destination-form.component').then((m) => m.DestinationFormComponent),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/destinations/:id/edit',
    loadComponent: () =>
      import('./publishing/destination-form.component').then((m) => m.DestinationFormComponent),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/destinations/:id',
    loadComponent: () =>
      import('./publishing/destination-details.component').then(
        (m) => m.DestinationDetailsComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/new',
    loadComponent: () =>
      import('./publishing/publish-new.component').then((m) => m.PublishNewComponent),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/executions',
    loadComponent: () =>
      import('./publishing/execution-list.component').then((m) => m.ExecutionListComponent),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/executions/:id',
    loadComponent: () =>
      import('./publishing/execution-details.component').then((m) => m.ExecutionDetailsComponent),
    canActivate: [authGuard],
  },
  { path: 'workflows', ...placeholder('Workflows'), canActivate: [authGuard] },
  { path: 'approvals', ...placeholder('Approvals'), canActivate: [authGuard] },
  { path: 'execution-history', ...placeholder('Execution History'), canActivate: [authGuard] },
  { path: 'settings', ...placeholder('Settings'), canActivate: [authGuard] },
  { path: '**', redirectTo: 'dashboard' },
];
