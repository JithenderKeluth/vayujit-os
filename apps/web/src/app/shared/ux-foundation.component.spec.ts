import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { BreadcrumbsComponent } from './breadcrumbs.component';
import {
  EmptyStateComponent,
  ErrorStateComponent,
  LoadingStateComponent,
} from './state-components';
import { EvidenceCardComponent } from './evidence-card.component';
import { PageHeaderComponent } from './page-header.component';
import { StatusBadgeComponent } from './status-badge.component';

@Component({
  standalone: true,
  imports: [
    BreadcrumbsComponent,
    EmptyStateComponent,
    ErrorStateComponent,
    EvidenceCardComponent,
    LoadingStateComponent,
    PageHeaderComponent,
    StatusBadgeComponent,
  ],
  template: `
    <app-breadcrumbs [items]="[{ label: 'Home', url: '/dashboard' }, { label: 'Current' }]" />
    <app-page-header title="Test page" eyebrow="Test" description="Safe description" />
    <app-status-badge status="reconciliation_required" label="Review required" tone="warning" />
    <app-evidence-card
      title="Observed source"
      classification="OBSERVED"
      summary="Untrusted source text is rendered as text."
      source="fixture"
      [details]="[{ label: 'Confidence', value: 'UNKNOWN' }]"
    />
    <app-loading-state message="Loading test data" />
    <app-empty-state
      title="Nothing here"
      message="Create a record to begin."
      actionLabel="Create"
      (action)="created = true"
    />
    <app-error-state
      message="The request failed safely."
      retryLabel="Retry"
      (retry)="retried = true"
    />
  `,
})
class UxHostComponent {
  created = false;
  retried = false;
}

describe('UX-1 foundation components', () => {
  let fixture: ComponentFixture<UxHostComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UxHostComponent],
      providers: [provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(UxHostComponent);
    fixture.detectChanges();
  });

  it('renders accessible navigation, page structure, semantic status, and safe evidence', () => {
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('nav[aria-label="Breadcrumb"]')).not.toBeNull();
    expect(root.querySelector('h1')?.textContent).toContain('Test page');
    expect(root.querySelector('[data-status="reconciliation_required"]')?.textContent).toContain(
      'Review required',
    );
    expect(root.querySelector('details')).not.toBeNull();
    expect(root.textContent).toContain('Untrusted source text is rendered as text.');
  });

  it('exposes loading, empty, and retryable error states without throwing', () => {
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('[role="status"]')?.textContent).toContain('Loading test data');
    (root.querySelector('app-empty-state button') as HTMLButtonElement).click();
    (root.querySelector('app-error-state button') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(fixture.componentInstance.created).toBe(true);
    expect(fixture.componentInstance.retried).toBe(true);
  });
});
