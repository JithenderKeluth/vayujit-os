import { Routes } from '@angular/router';

import { PlaceholderPageComponent } from './placeholder-page.component';

const placeholder = (title: string) => ({
  component: PlaceholderPageComponent,
  data: { title },
});

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  { path: 'login', ...placeholder('Login') },
  { path: 'dashboard', ...placeholder('Dashboard') },
  { path: 'brands', ...placeholder('Brands') },
  { path: 'products', ...placeholder('Products') },
  { path: 'workflows', ...placeholder('Workflows') },
  { path: 'approvals', ...placeholder('Approvals') },
  { path: 'execution-history', ...placeholder('Execution History') },
  { path: 'settings', ...placeholder('Settings') },
  { path: '**', redirectTo: 'dashboard' },
];
