import fs from 'node:fs/promises';

export function registeredOperations(openapi, declarations) {
  return Object.entries(openapi.paths).flatMap(([route, operations]) =>
    Object.entries(operations)
      .filter(([method]) =>
        ['get', 'post', 'put', 'patch', 'delete', 'head', 'options'].includes(method),
      )
      .map(([method, operation]) => ({
        path: route,
        method: method.toUpperCase(),
        operation_id: operation.operationId,
        tags: operation.tags || [],
        summary: operation.summary || '',
        static_sources: declarations
          .filter((entry) => entry.method === method.toUpperCase() && entry.path === route)
          .map((entry) => entry.source),
        ui_coverage: 'NOT_INFERRED_FROM_REGISTRATION',
      })),
  );
}

if (process.argv[1]?.endsWith('runtime-inventory.mjs')) {
  const report = JSON.parse(await fs.readFile('docs/qa/initial-report.json', 'utf8'));
  const token = report.cleanup[0].database.match(/^vayujit_qa([a-f0-9]{16})_test$/)?.[1];
  if (!token) throw new Error('QA_INVENTORY_TOKEN_INVALID');
  const openapi = JSON.parse(await fs.readFile(`tmp/qa-agent/${token}/openapi.json`, 'utf8'));
  const inventory = JSON.parse(await fs.readFile('docs/qa/application-inventory.json', 'utf8'));
  await fs.writeFile(
    'docs/qa/runtime-api-inventory.json',
    JSON.stringify(registeredOperations(openapi, inventory.api_declarations), null, 2),
  );
}
