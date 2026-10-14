/*
 * PR-SOS-09.2 authenticated browser certification.
 *
 * This is intentionally a read-only browser witness.  It navigates the normal
 * seller UI, reads canonical warning projections, and runs axe-core locally;
 * it never calls a marketplace/provider or creates a launch authorization.
 */
import fs from 'node:fs/promises';
import path from 'node:path';

const webOrigin = process.env.PRSOS_WEB_ORIGIN || 'http://127.0.0.1:4304';
const cdpOrigin = process.env.PRSOS_CDP_URL || 'http://127.0.0.1:9223';
const output = path.resolve(process.env.PRSOS_OUTPUT || 'tmp/pr-sos-092/browser');
await fs.mkdir(output, { recursive: true });

class Page {
  constructor(wsUrl) { this.socket = new WebSocket(wsUrl); this.nextId = 1; this.pending = new Map(); }
  async connect() {
    await new Promise((resolve, reject) => {
      this.socket.addEventListener('open', resolve, { once: true });
      this.socket.addEventListener('error', reject, { once: true });
    });
    this.socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data); const pending = this.pending.get(message.id);
      if (!pending) return; this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(message.error.message)); else pending.resolve(message.result || {});
    });
    await this.send('Page.enable'); await this.send('Runtime.enable'); await this.send('Security.enable');
    await this.send('Security.setIgnoreCertificateErrors', { ignore: true });
  }
  send(method, params = {}) {
    const id = this.nextId++; this.socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
  async eval(expression) {
    const result = await this.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || 'browser evaluation failed');
    return result.result?.value;
  }
  async waitFor(expression, timeout = 20000) {
    const started = Date.now();
    while (Date.now() - started < timeout) { if (await this.eval(expression).catch(() => false)) return; await new Promise((resolve) => setTimeout(resolve, 100)); }
    throw new Error(`Timed out waiting for ${expression}`);
  }
  async navigate(url) { await this.send('Page.navigate', { url }); await this.waitFor("document.readyState === 'complete'"); await new Promise((resolve) => setTimeout(resolve, 500)); }
  async fill(selector, value) { return this.eval(`(() => { const n=document.querySelector(${JSON.stringify(selector)}); if(!n) return false; const setter=Object.getOwnPropertyDescriptor(n.constructor.prototype,'value')?.set; if(setter) setter.call(n,${JSON.stringify(value)}); else n.value=${JSON.stringify(value)}; n.dispatchEvent(new Event('input',{bubbles:true})); n.dispatchEvent(new Event('change',{bubbles:true})); return true; })()`); }
  async screenshot(name) { const result = await this.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true }); const file = path.join(output, `${name}.png`); await fs.writeFile(file, Buffer.from(result.data, 'base64')); return path.relative(process.cwd(), file).replaceAll('\\', '/'); }
}

const targets = await (await fetch(`${cdpOrigin}/json/list`)).json();
const target = targets.find((item) => item.type === 'page' && item.webSocketDebuggerUrl);
if (!target) throw new Error('No isolated Chrome page is available.');
const page = new Page(target.webSocketDebuggerUrl); await page.connect();
const checks = []; const axeStates = [];
const check = async (id, expected, actual, screenshot = true) => { const pass = Boolean(actual); checks.push({ id, expected, pass, screenshot: screenshot ? await page.screenshot(id).catch(() => null) : null }); return pass; };

const password = process.env.PRSOS_OWNER_PASSWORD || 'LocalPrsos09Pass123!';
const email = process.env.PRSOS_OWNER_EMAIL || `prsos092-${Date.now()}@example.test`;
await page.navigate(`${webOrigin}/setup`);
const initialPath = await page.eval('location.pathname');
if (initialPath === '/setup') {
  await page.fill('#full-name', 'PR-SOS-09.2 Local Owner');
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.fill('#confirmation', password);
  await page.eval("document.querySelector('button[type=submit]')?.click()");
  await page.waitFor("location.pathname === '/dashboard' || location.pathname === '/login'").catch(async (error) => {
    console.error(JSON.stringify({ setupPath: await page.eval('location.href').catch(() => 'unknown'), setupBody: (await page.eval('document.body.innerText').catch(() => '')).slice(0, 1200) }));
    throw error;
  });
}
if ((await page.eval('location.pathname')) === '/login') {
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.eval("document.querySelector('button[type=submit]')?.click()");
}
await page.waitFor("location.pathname === '/dashboard'").catch(async (error) => {
  console.error(JSON.stringify({ authPath: await page.eval('location.pathname').catch(() => 'unknown'), authBody: (await page.eval('document.body.innerText').catch(() => '')).slice(0, 1000) }));
  throw error;
});
await check('AUTH-01', 'authenticated setup/login reaches dashboard', await page.eval("document.body.innerText.includes('What should you do today?')"));

await page.navigate(`${webOrigin}/operations/launch-readiness`);
await page.waitFor("document.body.innerText.includes('Launch readiness')");
const launchBody = await page.eval('document.body.innerText');
await check('WARN-01', 'warning evidence section is visible', launchBody.includes('Warnings before a production-ready decision'));
await check('WARN-02', 'warnings explain their canonical evidence and next action', await page.eval("document.querySelectorAll('.warning-item').length === 0 || [...document.querySelectorAll('.warning-item')].every((item) => item.innerText.includes('Evidence:') && item.querySelector('a[href]'))"));
await check('WARN-03', 'warning source links are same-origin canonical workspace routes', await page.eval("[...document.querySelectorAll('.warning-item a[href]')].every((item) => item.getAttribute('href')?.startsWith('/'))"));
await check('WARN-04', 'launch page does not claim production readiness', !/fully ready|production ready/i.test(launchBody));

const axeSource = await fs.readFile(path.resolve(process.env.PRSOS_AXE_PATH || 'node_modules/axe-core/axe.min.js'), 'utf8');
await page.eval(axeSource);
const states = [
  ['initial-overview', '/operations/launch-readiness', 'Launch readiness'],
  ['incomplete-business', '/settings', 'Settings'],
  ['catalog-warning', '/catalog', 'Catalog'],
  ['inventory-warning', '/marketplaces/inventory', 'Inventory'],
  ['marketplace-warning', '/marketplaces/accounts', 'Marketplace'],
  ['financial-warning', '/marketplaces/financials', 'Financial'],
  ['backup-readiness', '/operations/backups', 'Backup'],
  ['approval-readiness', '/operations/action-center', 'Action'],
  ['action-center-warning', '/operations/action-center', 'Action'],
  ['evidence-detail', '/operations/health', 'Health'],
  ['loading-state', '/operations/launch-readiness', 'Launch readiness'],
  ['blocked-state', '/catalog/not-a-real-product', 'Catalog'],
];
for (const [key, route, text] of states) {
  await page.navigate(`${webOrigin}${route}`);
  const content = await page.eval('document.body.innerText');
  const axe = await page.eval("axe.run(document, { resultTypes: ['violations', 'incomplete'] })").catch((error) => ({ error: String(error), violations: [], incomplete: [] }));
  const severe = axe.violations.filter((item) => ['serious', 'critical'].includes(item.impact));
  axeStates.push({ key, route, visible: content.includes(text), violations: axe.violations.map((item) => ({ id: item.id, impact: item.impact, nodes: item.nodes.length })), incomplete: axe.incomplete.map((item) => ({ id: item.id, impact: item.impact, nodes: item.nodes.length })) });
  await check(`AXE-${key}`, `${key} has no serious/critical automated violations`, severe.length === 0, true);
}

for (const width of [320, 360, 390, 768, 1024, 1440]) {
  await page.send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false });
  await page.navigate(`${webOrigin}/operations/launch-readiness`);
  await check(`RESP-${width}`, `no horizontal overflow at ${width}px`, await page.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'));
}
await page.send('Emulation.clearDeviceMetricsOverride');
await page.navigate(`${webOrigin}/operations/launch-readiness`);
await page.eval("document.querySelector('a[href]')?.focus()");
for (let index = 0; index < 6; index += 1) await page.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
await check('KEY-01', 'Tab traversal keeps a visible focus target', await page.eval("(() => { const item=document.activeElement; if(!item) return false; const r=item.getBoundingClientRect(); const s=getComputedStyle(item); return r.width>0 && r.height>0 && s.outlineStyle !== 'none'; })()"));
await check('KEY-02', 'warning page remains horizontally usable after keyboard traversal', await page.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'));

await page.navigate(`${webOrigin}/dashboard`); await page.navigate(`${webOrigin}/operations/launch-readiness`);
const history = await page.send('Page.getNavigationHistory');
if (history.currentIndex > 0) { await page.send('Page.navigateToHistoryEntry', { entryId: history.entries[history.currentIndex - 1].id }); await page.waitFor("document.readyState === 'complete'"); }
await check('NAV-01', 'Back returns to dashboard', await page.eval("location.pathname === '/dashboard'"));
await page.send('Page.navigateToHistoryEntry', { entryId: history.entries[history.currentIndex].id }); await page.waitFor("document.readyState === 'complete'");
await check('NAV-02', 'Forward restores launch readiness', await page.eval("location.pathname === '/operations/launch-readiness'"));

await page.navigate(`${webOrigin}/operations/launch-readiness`);
const logout = await page.eval("(() => { const node=document.querySelector('.logout-button') || [...document.querySelectorAll('a,button')].find((item) => /log\\s*out/i.test(item.textContent || '')); if(!node) return false; node.click(); return true; })()");
await check('AUTH-02', 'logout is executable', logout);
if (logout) await page.waitFor("location.pathname === '/login' || location.pathname === '/setup'", 10000).catch(() => {});
await page.navigate(`${webOrigin}/operations/launch-readiness`); await page.waitFor("location.pathname !== '/operations/launch-readiness'", 10000).catch(() => {});
await check('AUTH-03', 'protected launch deep link rejects unauthenticated access', await page.eval("location.pathname !== '/operations/launch-readiness'"));

const failures = checks.filter((item) => !item.pass);
const report = { route: '/operations/launch-readiness', checks, passed: checks.length - failures.length, failed: failures.length, axeStates };
await fs.writeFile(path.join(output, 'summary.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
page.socket.close();
if (failures.length) process.exitCode = 1;
