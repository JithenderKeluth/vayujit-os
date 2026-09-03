import { Routes } from '@angular/router';

import { AuthPageComponent } from './auth/auth-page.component';
import { authGuard, guestGuard } from './auth/auth.guards';
import { AdsWorkspaceComponent } from './ads/ads-workspace.component';
import { AdsOptimizationComponent } from './ads/ads-optimization.component';
import { MarketingPlanComponent } from './ads/marketing-plan.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  { path: 'setup', component: AuthPageComponent, canActivate: [guestGuard] },
  { path: 'login', component: AuthPageComponent, canActivate: [guestGuard] },
  {
    path: 'ads',
    component: AdsWorkspaceComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/create',
    component: AdsWorkspaceComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/calendar',
    component: AdsWorkspaceComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/accounts/:id',
    component: AdsWorkspaceComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/campaigns/:id',
    component: AdsWorkspaceComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/accounts',
    component: AdsWorkspaceComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/campaigns',
    component: AdsWorkspaceComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/analytics',
    component: AdsWorkspaceComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/recovery',
    component: AdsWorkspaceComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/settings',
    component: AdsWorkspaceComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/marketing',
    component: MarketingPlanComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/optimization',
    component: AdsOptimizationComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/recommendations',
    component: AdsOptimizationComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/optimization-rules',
    component: AdsOptimizationComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/anomalies',
    component: AdsOptimizationComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/experiments',
    component: AdsOptimizationComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/optimization-history',
    component: AdsOptimizationComponent,
    canActivate: [authGuard],
  },
  {
    path: 'ads/comparison',
    component: AdsOptimizationComponent,
    canActivate: [authGuard],
  },
  {
    path: 'dashboard',
    loadComponent: () =>
      import('./operations/dashboard.component').then((m) => m.DashboardComponent),
    canActivate: [authGuard],
  },
  {
    path: 'intelligence/sourcing',
    loadComponent: () =>
      import('./intelligence/sourcing-workspace.component').then(
        (m) => m.SourcingWorkspaceComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'intelligence/alibaba',
    loadComponent: () =>
      import('./intelligence/alibaba-discovery.component').then((m) => m.AlibabaDiscoveryComponent),
    canActivate: [authGuard],
  },
  {
    path: 'intelligence/indiamart',
    loadComponent: () =>
      import('./intelligence/indiamart-discovery.component').then(
        (m) => m.IndiaMartDiscoveryComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'intelligence/websites',
    loadComponent: () =>
      import('./intelligence/website-intelligence.component').then(
        (m) => m.WebsiteIntelligenceComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'intelligence/external',
    loadComponent: () =>
      import('./intelligence/external-research-workspace.component').then(
        (m) => m.ExternalResearchWorkspaceComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'intelligence/autonomous',
    loadComponent: () =>
      import('./intelligence/autonomous-research.component').then(
        (m) => m.AutonomousResearchComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'intelligence',
    loadComponent: () =>
      import('./intelligence/intelligence-workspace.component').then(
        (m) => m.IntelligenceWorkspaceComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'campaigns',
    loadComponent: () =>
      import('./campaigns/campaign-list.component').then((m) => m.CampaignListComponent),
    canActivate: [authGuard],
  },
  {
    path: 'campaigns/new',
    loadComponent: () =>
      import('./campaigns/campaign-form.component').then((m) => m.CampaignFormComponent),
    canActivate: [authGuard],
  },
  {
    path: 'campaigns/:id/video/:activityId',
    loadComponent: () =>
      import('./campaigns/campaign-video.component').then((m) => m.CampaignVideoComponent),
    canActivate: [authGuard],
  },
  {
    path: 'campaigns/:id/video',
    loadComponent: () =>
      import('./campaigns/campaign-video.component').then((m) => m.CampaignVideoComponent),
    canActivate: [authGuard],
  },
  {
    path: 'campaigns/:id/activities/new',
    loadComponent: () =>
      import('./campaigns/activity-form.component').then((m) => m.ActivityFormComponent),
    canActivate: [authGuard],
  },
  {
    path: 'campaigns/:id/dependencies',
    loadComponent: () =>
      import('./campaigns/dependency-editor.component').then((m) => m.DependencyEditorComponent),
    canActivate: [authGuard],
  },
  {
    path: 'campaigns/:id',
    loadComponent: () =>
      import('./campaigns/campaign-detail.component').then((m) => m.CampaignDetailComponent),
    canActivate: [authGuard],
  },
  {
    path: 'calendar',
    loadComponent: () =>
      import('./campaigns/content-calendar.component').then((m) => m.ContentCalendarComponent),
    canActivate: [authGuard],
  },
  {
    path: 'social',
    loadComponent: () =>
      import('./social/social-workspace.component').then((m) => m.SocialWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'social/compose',
    loadComponent: () =>
      import('./social/social-workspace.component').then((m) => m.SocialWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'social/channel',
    loadComponent: () =>
      import('./social/social-workspace.component').then((m) => m.SocialWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'social/accounts',
    loadComponent: () =>
      import('./social/social-workspace.component').then((m) => m.SocialWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'social/analytics',
    loadComponent: () =>
      import('./social/social-workspace.component').then((m) => m.SocialWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'social/posts/:id',
    loadComponent: () =>
      import('./social/social-workspace.component').then((m) => m.SocialWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'social/recovery',
    loadComponent: () =>
      import('./social/social-workspace.component').then((m) => m.SocialWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'social/settings',
    loadComponent: () =>
      import('./social/social-workspace.component').then((m) => m.SocialWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces',
    loadComponent: () =>
      import('./marketplaces/marketplace-home.component').then((m) => m.MarketplaceHomeComponent),
    canActivate: [authGuard],
  },
  { path: 'marketplaces/overview', redirectTo: 'marketplaces', pathMatch: 'full' },
  {
    path: 'marketplaces/video',
    loadComponent: () =>
      import('./marketplaces/marketplace-video.component').then((m) => m.MarketplaceVideoComponent),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/flipkart',
    loadComponent: () =>
      import('./marketplaces/flipkart-workspace.component').then(
        (m) => m.FlipkartWorkspaceComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/listings/:id/flipkart',
    loadComponent: () =>
      import('./marketplaces/flipkart-workspace.component').then(
        (m) => m.FlipkartWorkspaceComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/meesho',
    loadComponent: () =>
      import('./marketplaces/meesho-workspace.component').then((m) => m.MeeshoWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/listings/:id/meesho',
    loadComponent: () =>
      import('./marketplaces/meesho-workspace.component').then((m) => m.MeeshoWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/amazon',
    loadComponent: () =>
      import('./marketplaces/amazon-workspace.component').then((m) => m.AmazonWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/listings/:id/amazon',
    loadComponent: () =>
      import('./marketplaces/amazon-workspace.component').then((m) => m.AmazonWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/accounts',
    loadComponent: () =>
      import('./marketplaces/marketplace-accounts.component').then(
        (m) => m.MarketplaceAccountsComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/listings',
    loadComponent: () =>
      import('./marketplaces/marketplace-listings.component').then(
        (m) => m.MarketplaceListingsComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/inventory',
    loadComponent: () =>
      import('./marketplaces/marketplace-inventory.component').then(
        (m) => m.MarketplaceInventoryComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/orders',
    loadComponent: () =>
      import('./marketplaces/marketplace-orders.component').then(
        (m) => m.MarketplaceOrdersComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/settlements',
    loadComponent: () =>
      import('./marketplaces/marketplace-settlements.component').then(
        (m) => m.MarketplaceSettlementsComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'marketplaces/analytics',
    loadComponent: () =>
      import('./marketplaces/marketplace-analytics.component').then(
        (m) => m.MarketplaceAnalyticsComponent,
      ),
    canActivate: [authGuard],
  },
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
    path: 'products/:id/channels',
    loadComponent: () =>
      import('./marketplaces/product-channel-view.component').then(
        (m) => m.ProductChannelViewComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'products/:id/media',
    loadComponent: () =>
      import('./products/product-media.component').then((m) => m.ProductMediaComponent),
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
    path: 'ai/studio',
    loadComponent: () => import('./ai/ai-studio.component').then((m) => m.AIStudioComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/images/assets/:outputId',
    loadComponent: () =>
      import('./ai/ai-image-review.component').then((m) => m.AIImageReviewComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/video/bulk',
    loadComponent: () => import('./ai/ai-video-bulk.component').then((m) => m.AIVideoBulkComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/video',
    loadComponent: () => import('./ai/ai-video.component').then((m) => m.AIVideoComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/images',
    loadComponent: () =>
      import('./ai/ai-image-studio.component').then((m) => m.AIImageStudioComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/studio/seo',
    loadComponent: () => import('./ai/ai-seo.component').then((m) => m.AISeoComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/studio/bulk',
    loadComponent: () => import('./ai/ai-bulk.component').then((m) => m.AIBulkComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/studio/artifacts/:id/compare',
    loadComponent: () =>
      import('./ai/ai-artifact.component').then((module) => module.AIArtifactComponent),
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
    path: 'ai/brand-voices',
    loadComponent: () =>
      import('./ai/brand-voice-workspace.component').then((m) => m.BrandVoiceWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/presets',
    loadComponent: () =>
      import('./ai/preset-workspace.component').then((m) => m.PresetWorkspaceComponent),
    canActivate: [authGuard],
  },
  {
    path: 'ai/usage',
    loadComponent: () =>
      import('./ai/ai-usage.component').then((module) => module.AIUsageComponent),
    canActivate: [authGuard],
  },
  {
    path: 'settings/ai/providers',
    loadComponent: () =>
      import('./ai/ai-provider-settings.component').then(
        (module) => module.AIProviderSettingsComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'settings/ai/providers/openai-compatible',
    loadComponent: () =>
      import('./ai/ai-provider-settings.component').then(
        (module) => module.AIProviderSettingsComponent,
      ),
    canActivate: [authGuard],
  },
  {
    path: 'settings/publishing/connectors',
    redirectTo: 'settings/publishing/connectors/wordpress',
    pathMatch: 'full',
  },
  {
    path: 'settings/publishing/connectors/wordpress',
    loadComponent: () =>
      import('./publishing/wordpress-settings.component').then((m) => m.WordPressSettingsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'settings/publishing/connectors/shopify',
    loadComponent: () =>
      import('./publishing/shopify-settings.component').then((m) => m.ShopifySettingsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/destinations/shopify',
    redirectTo: 'publishing/destinations/new',
    pathMatch: 'full',
  },
  {
    path: 'publishing/destinations/wordpress',
    redirectTo: 'publishing/destinations/new',
    pathMatch: 'full',
  },
  {
    path: 'media',
    loadComponent: () => import('./media/media-list.component').then((m) => m.MediaListComponent),
    canActivate: [authGuard],
  },
  {
    path: 'media/upload',
    loadComponent: () =>
      import('./media/media-upload.component').then((m) => m.MediaUploadComponent),
    canActivate: [authGuard],
  },
  {
    path: 'media/:id',
    loadComponent: () =>
      import('./media/media-details.component').then((m) => m.MediaDetailsComponent),
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
  {
    path: 'publishing/schedules',
    loadComponent: () =>
      import('./publishing/schedules.component').then((m) => m.SchedulesComponent),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/schedules/new',
    loadComponent: () =>
      import('./publishing/schedules.component').then((m) => m.SchedulesComponent),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/schedules/:id',
    loadComponent: () =>
      import('./publishing/schedule-details.component').then((m) => m.ScheduleDetailsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/jobs',
    loadComponent: () => import('./publishing/jobs.component').then((m) => m.JobsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'publishing/jobs/:id',
    loadComponent: () =>
      import('./publishing/job-details.component').then((m) => m.JobDetailsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/workers',
    loadComponent: () => import('./publishing/workers.component').then((m) => m.WorkersComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/workers/:id',
    loadComponent: () =>
      import('./publishing/worker-details.component').then((m) => m.WorkerDetailsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'workflows',
    loadComponent: () =>
      import('./workflows/workflow-list.component').then((m) => m.WorkflowListComponent),
    canActivate: [authGuard],
  },
  {
    path: 'workflows/new',
    loadComponent: () =>
      import('./workflows/workflow-new.component').then((m) => m.WorkflowNewComponent),
    canActivate: [authGuard],
  },
  {
    path: 'workflows/:id',
    loadComponent: () =>
      import('./workflows/workflow-details.component').then((m) => m.WorkflowDetailsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'approvals',
    loadComponent: () =>
      import('./operations/approvals.component').then((m) => m.ApprovalsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'approvals/:id',
    loadComponent: () => import('./ai/ai-artifact.component').then((m) => m.AIArtifactComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations',
    loadComponent: () =>
      import('./operations/control-center.component').then((m) => m.ControlCenterComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/jobs',
    loadComponent: () =>
      import('./operations/control-center.component').then((m) => m.ControlCenterComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/providers',
    loadComponent: () =>
      import('./operations/control-center.component').then((m) => m.ControlCenterComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/storage',
    loadComponent: () =>
      import('./operations/control-center.component').then((m) => m.ControlCenterComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/security',
    loadComponent: () =>
      import('./operations/control-center.component').then((m) => m.ControlCenterComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/releases',
    loadComponent: () =>
      import('./operations/control-center.component').then((m) => m.ControlCenterComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/configuration',
    loadComponent: () =>
      import('./operations/control-center.component').then((m) => m.ControlCenterComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/health',
    loadComponent: () => import('./operations/health.component').then((m) => m.HealthComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/recovery',
    loadComponent: () => import('./operations/recovery.component').then((m) => m.RecoveryComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/backups',
    loadComponent: () => import('./operations/backups.component').then((m) => m.BackupsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'operations/audit',
    loadComponent: () =>
      import('./operations/execution-history.component').then((m) => m.ExecutionHistoryComponent),
    canActivate: [authGuard],
  },
  {
    path: 'execution-history',
    loadComponent: () =>
      import('./operations/execution-history.component').then((m) => m.ExecutionHistoryComponent),
    canActivate: [authGuard],
  },
  {
    path: 'settings',
    loadComponent: () => import('./operations/settings.component').then((m) => m.SettingsComponent),
    canActivate: [authGuard],
  },
  {
    path: 'settings/:section',
    loadComponent: () => import('./operations/settings.component').then((m) => m.SettingsComponent),
    canActivate: [authGuard],
  },
  { path: '**', redirectTo: 'dashboard' },
];
