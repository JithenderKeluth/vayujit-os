import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import { archiveQaReports } from './archive-reports.mjs';
const target = 'docs/qa/phase-4b-baseline.json';
await archiveQaReports();
const paths = [
  'apps/api/vayujit_api/commerce/inventory_router.py',
  'apps/api/vayujit_api/commerce/schemas.py',
  'apps/api/vayujit_api/commerce/models.py',
  'apps/api/vayujit_api/products/models.py',
  'apps/api/vayujit_api/catalog/models.py',
  'apps/web/src/app/marketplaces/unified-inventory.component.ts',
  'apps/web/src/app/marketplaces/marketplace.service.ts',
  'apps/web/src/app/app.routes.ts',
  'qa/tests/phase4.spec.mjs',
];
const source_sha256 = Object.fromEntries(
  await Promise.all(
    paths.map(async (p) => [
      p,
      crypto
        .createHash('sha256')
        .update(await fs.readFile(p))
        .digest('hex'),
    ]),
  ),
);
const backlog = JSON.parse(await fs.readFile('docs/qa/defect-backlog.json', 'utf8'));
await fs.writeFile(
  target,
  JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      source_sha256,
      findings: backlog,
      phase4a: JSON.parse(await fs.readFile('docs/qa/phase-4a-resolution.json', 'utf8')).status,
      contract_audit: [
        'Opening ledger and audit already exist.',
        'Replay compares only item/key, not intent.',
        'Creation lacks concurrency serialization.',
        'Text is trimmed only after lookup; whitespace and physical-product eligibility are not enforced.',
        'Supplier/cost/reason input is not required; reason is canonically Opening balance.',
        'One item is unique per owner + SKU + location, not per product; variants and multiple locations are supported.',
      ],
    },
    null,
    2,
  ),
  { flag: 'wx' },
);
console.log('Preserved Phase 4B baseline; no business state changed.');
