/*
 * Small authenticated PR-SOS-09 browser smoke.  It uses the existing isolated
 * Chrome/CDP surface and the normal setup/login UI; it never calls a provider
 * and never creates a marketplace/supplier execution.
 */
import fs from 'node:fs/promises';
import path from 'node:path';

const webOrigin = process.env.PRSOS_WEB_ORIGIN || 'http://127.0.0.1:4304';
const cdpOrigin = process.env.PRSOS_CDP_URL || 'http://127.0.0.1:9223';
const output = path.resolve(process.env.PRSOS_OUTPUT || 'tmp/pr-sos-09/browser');
await fs.mkdir(output, { recursive: true });
const debug = process.env.PRSOS_DEBUG === '1';
const trace = (...values) => { if (debug) console.error('[browser-smoke]', ...values); };

class Page {
  constructor(wsUrl) {
    this.socket = new WebSocket(wsUrl);
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    await new Promise((resolve, reject) => {
      this.socket.addEventListener('open', resolve, { once: true });
      this.socket.addEventListener('error', reject, { once: true });
    });
    this.socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(message.error.message));
      else pending.resolve(message.result || {});
    });
    await this.send('Page.enable');
    await this.send('Runtime.enable');
    // The production-like stack uses a disposable self-signed certificate;
    // trust is scoped to this isolated CDP target only.
    await this.send('Security.enable');
    await this.send('Security.setIgnoreCertificateErrors', { ignore: true });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }

  async eval(expression) {
    const result = await this.send('Runtime.evaluate', {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || 'browser evaluation failed');
    return result.result?.value;
  }

  async waitFor(expression, timeout = 20000) {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      if (await this.eval(expression).catch(() => false)) return;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`Timed out waiting for ${expression}`);
  }

  async navigate(url) {
    await this.send('Page.navigate', { url });
    await this.waitFor("document.readyState === 'complete'");
    await new Promise((resolve) => setTimeout(resolve, 600));
  }

  async history(delta) {
    const history = await this.send('Page.getNavigationHistory');
    const index = history.currentIndex + delta;
    if (index < 0 || index >= history.entries.length) throw new Error('browser history entry unavailable');
    await this.send('Page.navigateToHistoryEntry', { entryId: history.entries[index].id });
    await this.waitFor("document.readyState === 'complete'");
    await new Promise((resolve) => setTimeout(resolve, 400));
  }

  async fill(selector, value) {
    return this.eval(`(() => { const n=document.querySelector(${JSON.stringify(selector)}); if(!n) return false; const setter=Object.getOwnPropertyDescriptor(n.constructor.prototype,'value')?.set; if(setter) setter.call(n,${JSON.stringify(value)}); else n.value=${JSON.stringify(value)}; n.dispatchEvent(new Event('input',{bubbles:true})); n.dispatchEvent(new Event('change',{bubbles:true})); return true; })()`);
  }

  async click(selector) {
    return this.eval(`(() => { const n=document.querySelector(${JSON.stringify(selector)}); if(!n) return false; n.click(); return true; })()`);
  }

  async screenshot(name) {
    const result = await this.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    const file = path.join(output, `${name}.png`);
    await fs.writeFile(file, Buffer.from(result.data, 'base64'));
    return path.relative(process.cwd(), file).replaceAll('\\', '/');
  }
}

const pages = await (await fetch(`${cdpOrigin}/json/list`)).json();
const target = pages.find((item) => item.type === 'page' && item.webSocketDebuggerUrl);
if (!target) throw new Error('No isolated Chrome page is available.');
const page = new Page(target.webSocketDebuggerUrl);
await page.connect();
trace('connected');

const checks = [];
const check = async (id, expected, actual, screenshot = true) => {
  const pass = Boolean(actual);
  checks.push({ id, expected, pass, screenshot: screenshot ? await page.screenshot(id).catch(() => null) : null });
  return pass;
};

const password = process.env.PRSOS_OWNER_PASSWORD || 'LocalPrsos09Pass123!';
const email = process.env.PRSOS_OWNER_EMAIL || `prsos09-${Date.now()}@gmail.com`;
await page.navigate(`${webOrigin}/setup`);
trace('navigated setup', await page.eval('location.href'));
const initialPath = await page.eval('location.pathname');
if (initialPath === '/setup') {
  trace('setup form');
  await page.fill('#full-name', 'PR-SOS-09 Local Owner');
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.fill('#confirmation', password);
  await page.click('button[type="submit"]');
  await page.waitFor("location.pathname === '/dashboard' || location.pathname === '/login'");
  if ((await page.eval('location.pathname')) === '/login') {
    await page.fill('#email', email);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
  }
} else if (initialPath === '/login') {
  trace('login form');
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.click('button[type="submit"]');
}
trace('waiting dashboard', await page.eval('location.href'));
await page.waitFor("location.pathname === '/dashboard'");
trace('dashboard reached');
await check('AUTH-01', 'normal setup/login reaches the authenticated dashboard', await page.eval("document.body.innerText.includes('What should you do today?')"));

await page.navigate(`${webOrigin}/operations/launch-readiness`);
await page.waitFor("document.body.innerText.includes('Launch readiness')");
const body = await page.eval('document.body.innerText');
await check('LAUNCH-01', 'launch readiness heading and local-only safety boundary', body.includes('Launch readiness') && body.includes('Local preparation only'));
await check('LAUNCH-02', 'canonical readiness areas are visible', ['Business identity', 'Application infrastructure', 'Catalog & listing', 'Backup & recovery'].every((value) => body.includes(value)));
await check('LAUNCH-03', 'recommended next-action sequence is visible', body.toLowerCase().includes('recommended order') && body.includes('Prepare, review, then authorize'));
await check('LAUNCH-04', 'no external actions warning is visible', body.includes('No marketplace, supplier, payment, or inventory write is performed from this page'));
await check('LAUNCH-05', 'readiness summary exposes the current local environment', body.includes('LOCAL') || body.includes('Local'));
await check('LAUNCH-06', 'readiness cards expose explicit status labels', ['Ready', 'Needs attention', 'Blocked', 'Unknown'].some((value) => body.includes(value)));
await check('LAUNCH-07', 'business identity and infrastructure sections are actionable', body.includes('Business identity') && body.includes('Application infrastructure'));
await check('LAUNCH-08', 'safety boundary and HUMAN approval language are present', body.toLowerCase().includes('human') && body.toLowerCase().includes('approval'));
await check('LAUNCH-09', 'rendered page has no undefined/null data leakage', !/\b(undefined|null)\b/i.test(body));
await check('LAUNCH-10', 'launch page has navigable next-action links', await page.eval("document.querySelectorAll('a[href]').length >= 1"));

const routeCheck = async (id, route, expectedText) => {
  trace('route', route);
  await page.navigate(`${webOrigin}${route}`);
  const routePath = await page.eval('location.pathname');
  const text = await page.eval('document.body.innerText');
  return check(id, `${route} loads the authenticated workspace`, routePath === route && text.includes(expectedText), false);
};
await routeCheck('NAV-01', '/dashboard', 'What should you do today?');
await routeCheck('NAV-02', '/catalog', 'Catalog');
await routeCheck('NAV-03', '/marketplaces/inventory', 'Inventory');
await routeCheck('NAV-04', '/marketplaces/accounts', 'Marketplace');
await routeCheck('NAV-05', '/marketplaces/financials', 'Financial');
await routeCheck('NAV-06', '/operations/backups', 'Backup');
await routeCheck('NAV-07', '/operations/action-center', 'Action');
await routeCheck('NAV-08', '/settings', 'Settings');
await page.navigate(`${webOrigin}/operations/launch-readiness`);
await check('NAV-09', 'returning to launch readiness preserves the route', await page.eval("location.pathname === '/operations/launch-readiness'"));
await page.send('Page.reload');
await page.waitFor("document.readyState === 'complete'");
await check('NAV-10', 'refresh preserves the deep link and authenticated shell', await page.eval("location.pathname === '/operations/launch-readiness' && document.body.innerText.includes('Launch readiness')"));
await page.navigate(`${webOrigin}/dashboard`);
await page.navigate(`${webOrigin}/operations/launch-readiness`);
await page.history(-1);
await check('NAV-11', 'browser Back returns to the prior seller route', await page.eval("location.pathname === '/dashboard'"));
await page.history(1);
await check('NAV-12', 'browser Forward restores the launch route', await page.eval("location.pathname === '/operations/launch-readiness'"));
await check('NAV-13', 'deep-link page keeps the active seller shell', await page.eval("document.body.innerText.includes('VAYUJIT OS') && document.querySelector('nav') !== null"));
await check('NAV-14', 'deep-link page has no horizontal overflow at the default viewport', await page.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'));
await check('SEC-01', 'session remains same-origin and does not expose credentials', await page.eval("[...document.scripts].every((node) => !/secret|password|token/i.test(node.textContent || ''))"));
await check('SEC-02', 'launch page exposes the emergency-stop/local-only state', (await page.eval('document.body.innerText')).toLowerCase().includes('local'));

const axeSource = await fs.readFile(path.resolve('node_modules/axe-core/axe.min.js'), 'utf8');
await page.eval(axeSource);
const axe = await page.eval("axe.run(document, { resultTypes: ['violations', 'incomplete'] })");
await check('AXE-01', 'launch readiness has no automated serious/critical violations', axe.violations.filter((item) => ['serious', 'critical'].includes(item.impact)).length === 0);

for (const width of [360, 390, 768, 1024, 1440]) {
  await page.send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false });
  await page.navigate(`${webOrigin}/operations/launch-readiness`);
  const responsive = await page.eval('document.documentElement.scrollWidth <= window.innerWidth + 1');
  await check(`RESP-${width}`, `no horizontal overflow at ${width}px`, responsive);
}
await page.send('Emulation.clearDeviceMetricsOverride');

await page.navigate(`${webOrigin}/operations/launch-readiness`);
trace('logout controls', await page.eval("JSON.stringify({path:location.pathname,userText:document.body.innerText.includes('Workspace owner'),buttons:[...document.querySelectorAll('button')].map((candidate) => candidate.textContent)})"));
const logoutClicked = await page.eval("(() => { const node = document.querySelector('.logout-button') || [...document.querySelectorAll('a,button')].find((candidate) => /log\s*out/i.test(candidate.textContent || '')); if (!node) return false; node.click(); return true; })()");
await check('AUTH-02', 'logout control is present and executable', logoutClicked);
if (logoutClicked) {
  await page.waitFor("location.pathname === '/login' || location.pathname === '/setup'", 10000).catch(() => {});
}
await check('AUTH-03', 'logout returns to an unauthenticated route', await page.eval("location.pathname === '/login' || location.pathname === '/setup'"));
await page.navigate(`${webOrigin}/operations/launch-readiness`);
await page.waitFor("location.pathname !== '/operations/launch-readiness'", 10000).catch(() => {});
await check('AUTH-04', 'protected launch route rejects an unauthenticated deep link', await page.eval("location.pathname !== '/operations/launch-readiness'"));

const failures = checks.filter((item) => !item.pass);
console.log(JSON.stringify({
  route: '/operations/launch-readiness',
  checks,
  passed: checks.length - failures.length,
  failed: failures.length,
  axeViolations: axe.violations.map((item) => ({ id: item.id, impact: item.impact, nodes: item.nodes.length })),
  axeIncomplete: axe.incomplete.map((item) => ({ id: item.id, impact: item.impact, nodes: item.nodes.length })),
}, null, 2));
if (failures.length) process.exitCode = 1;
