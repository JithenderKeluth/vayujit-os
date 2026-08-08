import { Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

@Component({
  selector: 'app-amazon-workspace',
  template:
    '<section class="marketplace-page"><header><h1>Amazon Marketplace</h1><p>Preview approved content, submit safely, and reconcile asynchronous SP-API status.</p></header><article class="marketplace-card"><h2>Operator checklist</h2><ul><li>Confirm the India marketplace or another configured region.</li><li>Use preview to resolve required product attributes and media.</li><li>Submit only approved content with a stable idempotency key.</li><li>Reconcile processing listings before treating them as active.</li></ul><p class="muted">Real Amazon validation is not performed without operator credentials.</p></article></section>',
  styleUrl: './marketplaces.css',
})
export class AmazonWorkspaceComponent {
  private readonly route = inject(ActivatedRoute);
  readonly listingId = this.route.snapshot.paramMap.get('id');
}
