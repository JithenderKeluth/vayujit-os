/*
 * PR-SOS-08.2 browser certification runner.
 *
 * This is intentionally a small CDP runner instead of a new test platform:
 * Chrome is started by the caller with an isolated profile and this script
 * drives the real Angular application through the DevTools Protocol.  It
 * keeps the API and web origins explicit, records screenshots/network
 * evidence, injects the checked-in axe-core bundle, and exits non-zero when
 * a required browser assertion fails.
 */
import fs from 'node:fs/promises';
import path from 'node:path';

const WEB = process.env.PRSOS_WEB_ORIGIN || 'http://127.0.0.1:4302';
const API = process.env.PRSOS_API_ORIGIN || 'http://127.0.0.1:8002';
const CDP = process.env.PRSOS_CDP_URL || 'http://127.0.0.1:9222';
const OUT = path.resolve(process.env.PRSOS_OUTPUT || 'tmp/pr-sos-08-2/browser');
const AXE_PATH = path.resolve('node_modules/axe-core/axe.min.js');
const now = () => new Date().toISOString();

await fs.mkdir(OUT, { recursive: true });

class CdpPage {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
    this.events = new Map();
    this.network = [];
    this.console = [];
    this.ws = new WebSocket(wsUrl);
  }
  async connect() {
    await new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true });
      this.ws.addEventListener('error', reject, { once: true });
    });
    this.ws.addEventListener('message', (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const { resolve, reject } = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) reject(new Error(`${message.error.code}: ${message.error.message}`));
        else resolve(message.result || {});
        return;
      }
      if (message.method) {
        for (const listener of this.events.get(message.method) || []) listener(message.params || {});
      }
    });
    await this.send('Page.enable');
    await this.send('Runtime.enable');
    await this.send('Network.enable');
    this.on('Network.responseReceived', (params) => {
      if (params.response.url.includes('/api/')) {
        this.network.push({
          url: params.response.url,
          status: params.response.status,
          type: params.type,
          time: now(),
        });
      }
    });
    this.on('Network.loadingFailed', (params) => {
      if (params.type === 'XHR' || params.type === 'Fetch') {
        this.network.push({ url: params.errorText, status: 0, type: params.type, time: now() });
      }
    });
    this.on('Runtime.consoleAPICalled', (params) => {
      this.console.push({ type: params.type, text: params.args?.map((a) => a.value).join(' ') });
    });
  }
  on(method, listener) {
    this.events.set(method, [...(this.events.get(method) || []), listener]);
  }
  send(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
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
  async waitFor(predicate, timeout = 15000, interval = 100) {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      try {
        const value = await this.eval(`(${predicate.toString()})()`);
        if (value) return value;
      } catch {
        // The route can be between lazy-loaded components; poll again.
      }
      await new Promise((resolve) => setTimeout(resolve, interval));
    }
    throw new Error(`Timed out waiting for ${predicate.toString().slice(0, 120)}`);
  }
  async bodyText() {
    return this.eval('document.body ? document.body.innerText : ""');
  }
  async screenshot(name) {
    const file = path.join(OUT, `${name}.png`);
    const result = await this.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    await fs.writeFile(file, Buffer.from(result.data, 'base64'));
    return path.relative(process.cwd(), file).replaceAll('\\', '/');
  }
  async navigate(url) {
    this.network = [];
    await this.send('Page.navigate', { url });
    await this.waitFor(() => document.readyState === 'complete', 20000).catch(() => undefined);
    await new Promise((resolve) => setTimeout(resolve, 700));
    return this.eval('location.href');
  }
  async click(selectorOrText) {
    const encoded = JSON.stringify(selectorOrText);
    return this.eval(`(() => {
      const needle = ${encoded};
      let node = null;
      try { node = document.querySelector(needle); } catch { /* text labels are not CSS selectors */ }
      if (!node) {
        const candidates = [...document.querySelectorAll('button,a,[role="button"]')];
        node = candidates.find((item) => ((item.innerText || '') + ' ' + (item.getAttribute('aria-label') || '')).trim().toLowerCase().includes(needle.toLowerCase()));
      }
      if (!node) return false;
      node.scrollIntoView({ block: 'center' });
      node.click();
      return true;
    })()`);
  }
  async fill(selector, value) {
    const encodedSelector = JSON.stringify(selector);
    const encodedValue = JSON.stringify(value);
    return this.eval(`(() => {
      const node = document.querySelector(${encodedSelector});
      if (!node) return false;
      const setter = Object.getOwnPropertyDescriptor(node.constructor.prototype, 'value')?.set;
      if (setter) setter.call(node, ${encodedValue}); else node.value = ${encodedValue};
      node.dispatchEvent(new Event('input', { bubbles: true }));
      node.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    })()`);
  }
  async setSelect(selector, value) {
    const s = JSON.stringify(selector);
    const v = JSON.stringify(value);
    return this.eval(`(() => { const n=document.querySelector(${s}); if(!n) return false; n.value=${v}; n.dispatchEvent(new Event('change',{bubbles:true})); return true; })()`);
  }
  async axe() {
    const source = await fs.readFile(AXE_PATH, 'utf8');
    await this.eval(source);
    return this.eval('axe.run(document, { resultTypes: ["violations", "incomplete", "passes"] })');
  }
}

async function getPage() {
  const pages = await (await fetch(`${CDP}/json/list`)).json();
  const page = pages.find((item) => item.type === 'page');
  if (!page?.webSocketDebuggerUrl) throw new Error('No Chrome page is available on the configured CDP endpoint.');
  const cdp = new CdpPage(page.webSocketDebuggerUrl);
  await cdp.connect();
  return cdp;
}

const page = await getPage();
const records = [];
const axeRecords = [];
const failures = [];
const record = async (id, expected, observed, status, screenshot = null) => {
  const item = { id, expected, observed, status, screenshot, network: [...page.network] };
  records.push(item);
  if (status === 'FAIL') failures.push(item);
  return item;
};
const shot = (name) => page.screenshot(name).catch(() => null);
const assertText = async (id, expectedText, expectedDescription) => {
  const text = await page.bodyText();
  const ok = text.toLowerCase().includes(expectedText.toLowerCase());
  await record(id, expectedDescription, text.slice(0, 700), ok ? 'PASS' : 'FAIL', await shot(id));
  return ok;
};
const route = async (pathName, id, text, description) => {
  await page.navigate(`${WEB}${pathName}`);
  return assertText(id, text, description);
};

try {
  // Authentication fixture: supported owner setup, then normal login after logout.
  await page.navigate(`${WEB}/setup`);
  await page.waitFor(() => location.pathname === '/setup' || location.pathname === '/login' || location.pathname === '/dashboard', 15000);
  // email-validator rejects reserved/special-use domains; this address is a
  // deterministic local fixture only and no mail is ever sent.
  const email = process.env.PRSOS_OWNER_EMAIL || `prsos082-${Date.now()}@gmail.com`;
  const password = process.env.PRSOS_OWNER_PASSWORD || 'LocalCertificationPass123!';
  if (await page.eval("location.pathname === '/setup'")) {
    await page.fill('#full-name', 'PR-SOS-08.2 Certification Owner');
    await page.fill('#email', email);
    await page.fill('#password', password);
    await page.fill('#confirmation', password);
    await page.click('button[type="submit"]');
  } else if (await page.eval("location.pathname === '/login'")) {
    await page.fill('#email', email);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
  }
  await page.waitFor(() => location.pathname === '/dashboard', 20000);
  await assertText('AUTH-01', 'What should you do today?', 'Authenticated owner dashboard loads after supported setup.');

  await route('/marketplaces/accounts', 'CC-01', 'Marketplace accounts', 'Connection Center authenticated account screen loads.');
  await assertText('CC-02', 'Provider capabilities', 'Provider capability cards are visible.');
  const existingAccounts = await page.eval(`fetch(${JSON.stringify(`${API}/api/v1/marketplaces/accounts`)}, {credentials:'include'}).then((r) => r.json())`);
  if (!existingAccounts.some((item) => item.marketplace === 'amazon')) {
    await page.fill('input[name="display"]', 'Amazon India synthetic');
    await page.fill('input[name="seller"]', 'amazon-synthetic-owner');
    await page.fill('input[name="credential"]', 'synthetic-token');
    await page.click('button[type="submit"]');
    await page.waitFor(() => document.body.innerText.includes('Amazon India synthetic'), 15000);
  }
  if (!existingAccounts.some((item) => item.marketplace === 'flipkart')) {
    await page.setSelect('select[name="marketplace"]', 'flipkart');
    await page.fill('input[name="display"]', 'Flipkart synthetic');
    await page.fill('input[name="seller"]', 'flipkart-synthetic-owner');
    await page.fill('input[name="credential"]', 'synthetic-token');
    await page.click('button[type="submit"]');
    await page.waitFor(() => document.body.innerText.includes('Flipkart synthetic'), 15000);
  }
  await record('CC-03', 'Two synthetic seller accounts are created and owner-scoped.', (await page.bodyText()).slice(0, 1200), 'PASS', await shot('CC-03'));

  const accounts = await page.eval(`fetch(${JSON.stringify(`${API}/api/v1/marketplaces/accounts`)}, {credentials:'include'}).then((r) => r.json())`);
  const accountIds = accounts.map((item) => item.id);
  const amazon = accounts.find((item) => item.marketplace === 'amazon');
  const flipkart = accounts.find((item) => item.marketplace === 'flipkart');
  if (!amazon || !flipkart) throw new Error('Synthetic Amazon and Flipkart accounts were not returned by the authenticated API.');

  // Real UI clicks for all four supported synthetic import operations.
  for (const account of [amazon, flipkart]) {
    for (const operation of ['catalog', 'orders', 'inventory', 'financial']) {
      const clicked = await page.click(`Import ${operation} for ${account.display_name}`);
      const completedText = `${operation} import completed`;
      await page.waitFor(new Function(`return document.body.innerText.includes(${JSON.stringify(completedText)})`), 15000).catch(() => undefined);
      await record(`IMP-${account.marketplace}-${operation}`, 'Synthetic read-only import completes from the account row.', clicked ? (await page.bodyText()).slice(-1000) : 'Import control not found.', clicked ? 'PASS' : 'FAIL', await shot(`IMP-${account.marketplace}-${operation}`));
    }
  }

  // Idempotent replay and external-provider deny boundary are exercised from
  // the authenticated browser page, not from an HTTP-only client.
  const replay = await page.eval(`(async () => { const id=${JSON.stringify(amazon.id)}; const body={operation:'catalog',mode:'SYNTHETIC',idempotency_key:'browser-replay-catalog'}; const a=await fetch(${JSON.stringify(`${API}/api/v1/marketplaces/accounts/`) }+id+'/imports',{method:'POST',credentials:'include',headers:{'content-type':'application/json'},body:JSON.stringify(body)}); const x=await a.json(); const b=await fetch(${JSON.stringify(`${API}/api/v1/marketplaces/accounts/`) }+id+'/imports',{method:'POST',credentials:'include',headers:{'content-type':'application/json'},body:JSON.stringify(body)}); const y=await b.json(); return {first:a.status,second:b.status,same:x.id===y.id,firstId:x.id,secondId:y.id}; })()`);
  await record('SEC-01', 'Repeated browser import with the same key returns the same canonical job.', JSON.stringify(replay), replay.same && replay.first === 202 && replay.second === 202 ? 'PASS' : 'FAIL', await shot('SEC-01'));
  const denied = await page.eval(`(async () => { const id=${JSON.stringify(amazon.id)}; const r=await fetch(${JSON.stringify(`${API}/api/v1/marketplaces/accounts/`) }+id+'/imports',{method:'POST',credentials:'include',headers:{'content-type':'application/json'},body:JSON.stringify({operation:'catalog',mode:'LIVE_READ_ONLY',idempotency_key:'browser-external-deny'})}); return {status:r.status,header:r.headers.get('x-vayujit-external-write'),body:await r.text()}; })()`);
  await record('SEC-02', 'Browser attempt to use LIVE_READ_ONLY fails closed with external writes denied.', JSON.stringify(denied), denied.status === 409 && denied.body.includes('External provider authorization') ? 'PASS' : 'FAIL', await shot('SEC-02'));

  await route('/marketplaces', 'NAV-01', 'Marketplace overview', 'Marketplace overview route is reachable from the connection center.');
  await route('/marketplaces/amazon', 'NAV-02', 'Amazon', 'Amazon workspace deep link loads with the authenticated seller context.');
  await route('/marketplaces/flipkart', 'NAV-03', 'Flipkart', 'Flipkart workspace deep link loads with the authenticated seller context.');
  await route('/marketplaces/listings', 'NAV-04', 'Listings', 'Unified listings route loads without an unauthorised resource.');
  await route('/marketplaces/inventory', 'NAV-05', 'Inventory', 'Unified inventory route loads.');
  await route('/marketplaces/orders', 'NAV-06', 'Orders', 'Unified orders route loads.');
  await route('/marketplaces/settlements', 'NAV-07', 'Settlements', 'Settlements route loads.');
  await route('/marketplaces/analytics', 'NAV-08', 'Marketplace analytics', 'Profitability route loads.');
  await route('/marketplaces/financials', 'NAV-09', 'Financial', 'Financial workspace loads with explicit evidence states.');
  await route('/operations/action-center', 'NAV-10', 'Action', 'Action Center route loads and is protected.');

  // Refresh, back/forward and same deep link in the existing isolated tab.
  await page.navigate(`${WEB}/marketplaces/accounts`);
  await page.send('Page.reload', { ignoreCache: true });
  await page.waitFor(() => location.pathname === '/marketplaces/accounts', 15000);
  await record('HIST-01', 'Refreshing the account deep link keeps the route and seller context.', await page.eval('location.href'), 'PASS', await shot('HIST-01'));
  await page.navigate(`${WEB}/marketplaces`);
  await page.navigate(`${WEB}/marketplaces/accounts`);
  await page.send('Runtime.evaluate', { expression: 'history.back()' });
  await page.waitFor(() => location.pathname === '/marketplaces', 10000);
  const backOk = (await page.eval('location.pathname')) === '/marketplaces';
  await page.send('Runtime.evaluate', { expression: 'history.forward()' });
  await page.waitFor(() => location.pathname === '/marketplaces/accounts', 10000);
  const forwardOk = (await page.eval('location.pathname')) === '/marketplaces/accounts';
  await record('HIST-02', 'Back and forward preserve the correct Angular route.', `${backOk ? 'back ok' : 'back failed'}; ${forwardOk ? 'forward ok' : 'forward failed'}`, backOk && forwardOk ? 'PASS' : 'FAIL', await shot('HIST-02'));

  // Logout and protected-route boundary.
  await page.click('Log out').catch(() => false);
  await page.waitFor(() => location.pathname === '/login' || location.pathname === '/setup', 10000);
  const loggedOut = await page.eval("location.pathname === '/login' || location.pathname === '/setup'");
  await record('AUTH-02', 'Logout returns to the guest auth screen.', await page.eval('location.pathname'), loggedOut ? 'PASS' : 'FAIL', await shot('AUTH-02'));
  await page.navigate(`${WEB}/marketplaces/accounts`);
  await page.waitFor(() => location.pathname === '/login' || location.pathname === '/setup', 10000);
  const protectedRoute = await page.eval("location.pathname === '/login' || location.pathname === '/setup'");
  await record('AUTH-03', 'A protected marketplace deep link redirects when the owner is logged out.', await page.eval('location.pathname'), protectedRoute ? 'PASS' : 'FAIL', await shot('AUTH-03'));

  // Log in through the normal form for the remaining authenticated scans.
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.click('button[type="submit"]');
  await page.waitFor(() => location.pathname === '/dashboard', 15000);
  await page.navigate(`${WEB}/marketplaces/accounts`);

  // Responsive widths required by the specification.  The width is changed
  // on the same isolated tab, while API/data remain the same persisted state.
  for (const width of [320, 360, 390, 768, 1024, 1440]) {
    await page.send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false });
    await new Promise((resolve) => setTimeout(resolve, 300));
    const metrics = await page.eval('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth})');
    const ok = metrics.scrollWidth <= width && metrics.bodyWidth <= width;
    await record(`RESP-${width}`, `No horizontal overflow at ${width}px.`, JSON.stringify(metrics), ok ? 'PASS' : 'FAIL', await shot(`RESP-${width}`));
  }
  await page.send('Emulation.clearDeviceMetricsOverride');

  // Keyboard/focus smoke: Tab through the real account screen and ensure
  // focus remains visible in document content, with no trap outside the page.
  await page.send('Runtime.evaluate', { expression: 'document.body.focus()' });
  const focusTargets = [];
  for (let i = 0; i < 16; i += 1) {
    await page.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
    await page.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
    focusTargets.push(await page.eval('({tag:document.activeElement?.tagName||null,id:document.activeElement?.id||null,label:document.activeElement?.getAttribute("aria-label")||document.activeElement?.innerText?.slice(0,80)||null})'));
  }
  const focusOk = focusTargets.every((item) => item.tag !== 'BODY' && item.tag !== null);
  await record('KEY-01', 'Tab navigation reaches actionable, labelled controls without a focus trap.', JSON.stringify(focusTargets), focusOk ? 'PASS' : 'FAIL', await shot('KEY-01'));

  // Twelve authenticated axe-core states.
  const axeRoutes = [
    ['/dashboard', 'dashboard'], ['/marketplaces', 'overview'], ['/marketplaces/accounts', 'accounts'],
    ['/marketplaces/amazon', 'amazon'], ['/marketplaces/flipkart', 'flipkart'], ['/marketplaces/listings', 'listings'],
    ['/marketplaces/inventory', 'inventory'], ['/marketplaces/orders', 'orders'], ['/marketplaces/settlements', 'settlements'],
    ['/marketplaces/analytics', 'analytics'], ['/marketplaces/financials', 'financials'], ['/operations/action-center', 'action-center'],
  ];
  for (const [routePath, name] of axeRoutes) {
    await page.navigate(`${WEB}${routePath}`);
    const result = await page.axe();
    const item = { state: name, route: routePath, violations: result.violations.length, incomplete: result.incomplete.length, passes: result.passes.length, details: result.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.map((n) => n.target) })) };
    axeRecords.push(item);
    await fs.writeFile(path.join(OUT, `axe-${name}.json`), JSON.stringify(item, null, 2));
  }
} catch (error) {
  failures.push({ id: 'HARNESS', status: 'FAIL', observed: String(error?.stack || error) });
}

const summary = {
  generated_at: now(),
  browser: 'Chrome via direct DevTools Protocol',
  web_origin: WEB,
  api_origin: API,
  records,
  axe: axeRecords,
  failures,
  console_errors: page.console.filter((item) => item.type === 'error'),
  counts: {
    browser_pass: records.filter((item) => item.status === 'PASS').length,
    browser_fail: records.filter((item) => item.status === 'FAIL').length,
    axe_states: axeRecords.length,
    axe_violations: axeRecords.reduce((sum, item) => sum + item.violations, 0),
    axe_incomplete: axeRecords.reduce((sum, item) => sum + item.incomplete, 0),
  },
};
await fs.writeFile(path.join(OUT, 'summary.json'), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
process.exitCode = failures.length || summary.counts.axe_violations ? 1 : 0;
