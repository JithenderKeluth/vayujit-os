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
  { path: 'brands', ...placeholder('Brands'), canActivate: [authGuard] },
  { path: 'products', ...placeholder('Products'), canActivate: [authGuard] },
  { path: 'workflows', ...placeholder('Workflows'), canActivate: [authGuard] },
  { path: 'approvals', ...placeholder('Approvals'), canActivate: [authGuard] },
  { path: 'execution-history', ...placeholder('Execution History'), canActivate: [authGuard] },
  { path: 'settings', ...placeholder('Settings'), canActivate: [authGuard] },
  { path: '**', redirectTo: 'dashboard' },
];
