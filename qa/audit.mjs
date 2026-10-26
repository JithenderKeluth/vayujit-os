import fs from 'node:fs/promises';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import ts from 'typescript';

export function componentPathForRoute(body, directName, imports, root) {
  const relative = body.match(/import\('([^']+)'\)/)?.[1] || imports.get(directName);
  return relative ? path.join(root, `${relative}.ts`) : null;
}

export async function audit({ write = true } = {}) {
  const root = path.resolve('apps/web/src/app');
  const routeSource = await fs.readFile(path.join(root, 'app.routes.ts'), 'utf8');
  const source = ts.createSourceFile('routes.ts', routeSource, ts.ScriptTarget.Latest, true);
  const imports = new Map();
  for (const statement of source.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier))
      continue;
    const bindings = statement.importClause?.namedBindings;
    if (bindings && ts.isNamedImports(bindings)) {
      for (const binding of bindings.elements)
        imports.set(binding.name.text, statement.moduleSpecifier.text);
    }
  }
  const files = [];
  async function walk(dir) {
    for (const item of await fs.readdir(dir, { withFileTypes: true })) {
      const file = path.join(dir, item.name);
      if (item.isDirectory()) await walk(file);
      else if (file.endsWith('.ts')) files.push(file);
    }
  }
  await walk(root);
  const navigation = await fs.readFile(
    path.join(root, 'shared/seller-navigation.component.ts'),
    'utf8',
  );
  const routes = [];
  function visit(node) {
    if (ts.isObjectLiteralExpression(node)) {
      const props = new Map(
        node.properties
          .filter(ts.isPropertyAssignment)
          .map((p) => [p.name.getText(source), p.initializer]),
      );
      const route = props.get('path');
      if (route && ts.isStringLiteral(route)) {
        const body = node.getText(source);
        const componentPath = componentPathForRoute(
          body,
          props.get('component')?.getText(source),
          imports,
          root,
        );
        const spec = componentPath?.replace(/\.ts$/, '.spec.ts');
        routes.push({
          route: `/${route.text}`,
          kind: props.has('redirectTo') ? 'REDIRECT' : 'PAGE',
          redirect: props.get('redirectTo')?.text || null,
          protected: body.includes('authGuard'),
          component: componentPath
            ? path.relative(process.cwd(), componentPath).replaceAll('\\', '/')
            : null,
          navigation: navigation.includes(`'/${route.text}'`)
            ? 'PRIMARY_OR_ADVANCED_NAV'
            : 'CONTEXTUAL_OR_DEEP_LINK_REVIEW',
          existing_unit_spec:
            spec && files.includes(spec)
              ? path.relative(process.cwd(), spec).replaceAll('\\', '/')
              : null,
          runtime_coverage: 'NOT_EXECUTED',
          risk: /catalog|product|auth|setup|login|financial|orders|inventory|approvals|business-agent|marketplaces/.test(
            route.text,
          )
            ? 'P0'
            : 'P1',
        });
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  const python = process.env.QA_PYTHON || path.resolve('apps/api/.venv/Scripts/python.exe');
  const backend = spawnSync(python, ['qa/audit_backend.py'], {
    encoding: 'utf8',
    maxBuffer: 30 * 1024 * 1024,
  });
  if (backend.status !== 0) throw new Error('BACKEND_STATIC_INVENTORY_FAILED');
  const data = JSON.parse(backend.stdout);
  const services = [];
  for (const file of files.filter((f) => f.endsWith('.service.ts'))) {
    services.push({
      source: path.relative(process.cwd(), file).replaceAll('\\', '/'),
      text: await fs.readFile(file, 'utf8'),
    });
  }
  for (const endpoint of data.api_declarations) {
    const suffix = endpoint.path
      .replace(/^\/api\/v1/, '')
      .split('/')
      .filter(Boolean)
      .slice(0, 2)
      .join('/');
    endpoint.frontend_candidates = services
      .filter((s) => suffix && s.text.includes(suffix))
      .map((s) => s.source);
    endpoint.ui_status = endpoint.frontend_candidates.length
      ? 'SERVICE_REFERENCE_CANDIDATE_NOT_UI_PROOF'
      : 'UNMAPPED_REVIEW_BACKEND_ONLY_OR_UI_GAP';
  }
  const result = {
    generated_at: new Date().toISOString(),
    methodology:
      'TypeScript AST route declarations + Python AST API/model declarations. References and test filenames are inventory, not executed coverage or proof of UI accessibility.',
    routes,
    ...data,
    frontend_specs: files
      .filter((f) => f.endsWith('.spec.ts'))
      .map((f) => path.relative(process.cwd(), f).replaceAll('\\', '/')),
  };
  if (!write) return result;
  await fs.mkdir('docs/qa', { recursive: true });
  await fs.writeFile('docs/qa/application-inventory.json', JSON.stringify(result, null, 2));
  const rows = routes.map(
    (r) =>
      `| ${r.route || '/'} | ${r.kind} | ${r.protected ? 'authGuard' : 'guest/redirect'} | ${r.navigation} | ${r.existing_unit_spec || 'NO_DIRECT_SPEC'} | ${r.risk} | NOT_EXECUTED |`,
  );
  await fs.writeFile(
    'docs/qa/coverage-matrix.md',
    `# QA source coverage inventory\n\n${result.methodology}\n\n${routes.length} route declarations; ${data.api_declarations.length} API declarations; ${data.models.length} models; ${data.backend_tests.length} backend test files; ${result.frontend_specs.length} Angular spec files.\n\nAll paths, API handlers, source locations, model tables, candidate frontend API references and test-file counts are in [application-inventory.json](application-inventory.json). API declarations are reconciled with actual OpenAPI in each disposable run. Dynamic bindings are not inferred as exact API coverage.\n\n| Route | Kind | Access | Discoverability | Existing spec (not rerun) | Risk | Phase 1 status |\n| --- | --- | --- | --- | --- | --- | --- |\n${rows.join('\n')}\n\nBackend endpoints without a static service reference are review candidates, not automatically missing features. Adapters, workers, internal ledgers and safety controls deliberately have no page. Deep links need persisted IDs before browser coverage.\n`,
  );
  return result;
}
if (process.argv[1]?.endsWith('audit.mjs')) {
  const result = await audit();
  console.log(
    `Inventory: ${result.routes.length} routes, ${result.api_declarations.length} API declarations, ${result.models.length} models.`,
  );
}
