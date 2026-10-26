import crypto from 'node:crypto';

export const surfaceId = (value) =>
  crypto.createHash('sha256').update(value).digest('hex').slice(0, 12);
export const areaOf = (route) => route.split('/').filter(Boolean)[0] || 'home';
export const canonicalRoute = (route) =>
  route.replace(/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/gi, ':id');

// Only legitimate persisted fixture identifiers are substituted. Never guess a
// UUID to count a 404 as a supported populated workflow.
export function routePlan(routes, manifest = {}) {
  return routes.map((r) => {
    let target = r.route;
    let reason = null;
    if (r.kind === 'REDIRECT') reason = 'REDIRECT_NOT_PAGE';
    else if (['/setup', '/login'].includes(target)) reason = 'GUEST_FLOW_SEPARATE_SCENARIO';
    else if (target.includes(':')) {
      let id;
      if (target.startsWith('/products/') || target.startsWith('/catalog/'))
        id = manifest.phase2?.product_id;
      else if (target.startsWith('/brands/')) id = manifest.brand_id;
      else if (target.startsWith('/intelligence/product-opportunities/'))
        id = manifest.phase2?.opportunity_id;
      if (!id || (target.match(/:/g) || []).length !== 1)
        reason = 'REQUIRES_UNAVAILABLE_CANONICAL_CONTEXT';
      else target = target.replace(/:[A-Za-z0-9_]+/, id);
    }
    return {
      ...r,
      target: reason ? null : target,
      disposition: reason || 'PLANNED_READ_ONLY_VISIT',
      area: areaOf(r.route),
    };
  });
}

export function classifyCoverage(planned, visits) {
  return planned.map((r) => {
    const actual = visits.filter((v) => v.declaration === r.route);
    return {
      declaration: r.route,
      kind: r.kind,
      area: r.area,
      source: r.component,
      status: actual.length
        ? actual.every((v) => v.route_match && !v.failure)
          ? 'VISITED_NOT_FULLY_TESTED'
          : 'OBSERVED_PROBLEM_REQUIRES_TRIAGE'
        : r.disposition,
      visits: actual.map((v) => ({
        project: v.project,
        route: v.route,
        evidence: v.evidence,
        control_count: v.controls.length,
      })),
    };
  });
}

export async function snapshotSurface(page, declaration, state) {
  const data = await page.evaluate(() => {
    const visible = (e) =>
      !!(e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden');
    const label = (e) =>
      (
        e.getAttribute('aria-label') ||
        (e.labels ? [...e.labels].map((l) => l.innerText).join(' ') : '') ||
        e.innerText ||
        e.getAttribute('title') ||
        e.getAttribute('name') ||
        ''
      )
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 180);
    const path = (href) => {
      try {
        return new URL(href, location.href).pathname;
      } catch {
        return null;
      }
    };
    const controls = [
      ...document.querySelectorAll(
        'a[href],button,input:not([type="hidden"]),select,textarea,summary,[role="tab"],[role="button"]',
      ),
    ].map((e, index) => ({
      index,
      tag: e.tagName.toLowerCase(),
      role: e.getAttribute('role'),
      name: label(e),
      type: e.getAttribute('type'),
      visible: visible(e),
      disabled: e.matches(':disabled') || e.getAttribute('aria-disabled') === 'true',
      required: e.hasAttribute('required') || e.getAttribute('aria-required') === 'true',
      href: e.tagName === 'A' ? path(e.href) : null,
      current: e.getAttribute('aria-current'),
      interaction: 'NOT_EXECUTED',
    }));
    return {
      route: location.pathname,
      headings: [...document.querySelectorAll('h1,h2,h3')].map((e) =>
        e.textContent.trim().slice(0, 180),
      ),
      controls,
      forms: [...document.querySelectorAll('form')].map((e) => ({
        name: e.getAttribute('aria-label'),
        inputs: e.querySelectorAll('input,select,textarea').length,
        visible: visible(e),
      })),
      dialogs: [...document.querySelectorAll('dialog,[role="dialog"]')].map((e) => ({
        name: label(e),
        visible: visible(e),
      })),
      tables: [...document.querySelectorAll('table')].map((e) => ({
        caption: e.querySelector('caption')?.textContent.trim() || null,
        rows: e.rows.length,
        columns: e.rows[0]?.cells.length || 0,
      })),
      state_text: [
        ...document.querySelectorAll(
          'app-empty-state,app-error-state,app-loading-state,[role="status"],[role="alert"]',
        ),
      ].map((e) => ({
        kind: e.tagName.toLowerCase(),
        role: e.getAttribute('role'),
        visible: visible(e),
        text: e.textContent.replace(/\s+/g, ' ').trim().slice(0, 500),
      })),
      placeholders: [...document.querySelectorAll('p,h2,h3')]
        .filter((e) => /coming soon|placeholder|not implemented/i.test(e.textContent))
        .map((e) => e.textContent.trim().slice(0, 300)),
      viewport: { width: innerWidth, height: innerHeight },
      document: {
        width: document.documentElement.scrollWidth,
        height: document.documentElement.scrollHeight,
      },
    };
  });
  data.controls = data.controls.map((c) => ({
    ...c,
    id: surfaceId(`${declaration}|${state}|${c.index}|${c.tag}|${c.name}|${c.href}`),
  }));
  return { declaration, state, ...data };
}

// Explicit action registry, not a crawler that guesses which buttons are safe.
export const approvedActions = Object.freeze({
  'inventory.refresh': { route: '/marketplaces/inventory', role: 'button', name: 'Refresh' },
  'product.save': { route: /^\/products\/[^/]+\/edit$/, role: 'button', name: 'Save product' },
  'auth.sign-in': { route: '/login', role: 'button', name: 'Sign in' },
});
export async function runApprovedAction(page, action) {
  const rule = approvedActions[action];
  const route = new URL(page.url()).pathname;
  if (!rule || (typeof rule.route === 'string' ? route !== rule.route : !rule.route.test(route)))
    throw new Error('QA_UNAPPROVED_INTERACTION');
  await page.getByRole(rule.role, { name: rule.name, exact: true }).click();
  return { action, route, result: 'CLICKED_EXPECTED_RESULT_REQUIRES_ASSERTION' };
}
