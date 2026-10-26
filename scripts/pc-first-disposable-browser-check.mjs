import fs from 'node:fs/promises';
import path from 'node:path';

const origin = process.env.PC_CERT_ORIGIN;
const email = process.env.PC_CERT_EMAIL;
const password = process.env.PC_CERT_PASSWORD;
const evidencePath = process.env.PC_CERT_EVIDENCE;
const screenshotDirectory = process.env.PC_CERT_SCREENSHOT_DIR;
const cdpPort = Number(process.env.PC_CERT_CDP_PORT);
if (!origin || !email || !password || !evidencePath || !screenshotDirectory || !cdpPort) {
  throw new Error('Isolated Chrome certification inputs are incomplete.');
}

const saved = JSON.parse(await fs.readFile(evidencePath, 'utf8'));
const report = { mode: 'isolated_chrome_disposable', checks: [], pages: [], viewports: [], axe: [], console_errors: [] };
const assert = (name, condition, evidence = '') => {
  report.checks.push({ name, pass: Boolean(condition), evidence });
  if (!condition) throw new Error(`Browser certification failed: ${name}${evidence ? ` (${evidence})` : ''}`);
};
const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const waitFor = async (expression, timeout = 15000) => {
  const until = Date.now() + timeout;
  while (Date.now() < until) {
    const value = await evaluate(expression);
    if (value) return value;
    await delay(200);
  }
  throw new Error(`Browser condition timed out: ${expression}`);
};

const version = await (await fetch(`http://127.0.0.1:${cdpPort}/json/version`)).json();
const targets = await (await fetch(`http://127.0.0.1:${cdpPort}/json`)).json();
let target = targets.find((item) => item.type === 'page' && item.url.startsWith(origin));
if (!target) {
  const created = await fetch(`http://127.0.0.1:${cdpPort}/json/new?${encodeURIComponent(`${origin}/login`)}`, { method: 'PUT' });
  target = await created.json();
}
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
let nextId = 0;
const pending = new Map();
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);
  if (message.method === 'Runtime.exceptionThrown') {
    report.console_errors.push(String(message.params.exceptionDetails?.text || 'Runtime exception').slice(0, 240));
  }
  if (!message.id) return;
  const waiter = pending.get(message.id);
  if (!waiter) return;
  pending.delete(message.id);
  if (message.error) waiter.reject(new Error(message.error.message));
  else waiter.resolve(message.result || {});
});
const command = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++nextId;
  pending.set(id, { resolve, reject });
  socket.send(JSON.stringify({ id, method, params }));
});
const evaluate = async (expression) => {
  const result = await command('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result?.value;
};
const navigate = async (url) => {
  await command('Page.navigate', { url });
  await waitFor("document.readyState === 'complete'");
  await delay(350);
  return evaluate('location.pathname');
};
const screenshot = async (name) => {
  const value = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await fs.writeFile(path.join(screenshotDirectory, name), Buffer.from(value.data, 'base64'));
};
const runAxe = async (pageName) => {
  const axe = await evaluate(`globalThis.axe ? true : false`);
  if (!axe) {
    const source = await fs.readFile(path.resolve('node_modules/axe-core/axe.min.js'), 'utf8');
    await evaluate(`${source}\n;globalThis.__pcAxeLoaded = true;`);
  }
  const results = await evaluate(`axe.run(document).then(r => ({
    violations: r.violations.map(v => ({ id: v.id, impact: v.impact, count: v.nodes.length, examples: v.nodes.slice(0,2).map(n => ({target: n.target, summary: n.failureSummary?.slice(0,180)})) })),
    passes: r.passes.length,
    incomplete: r.incomplete.map(v => ({ id: v.id, impact: v.impact, count: v.nodes.length, examples: v.nodes.slice(0,2).map(n => ({target: n.target, summary: n.failureSummary?.slice(0,180)})) })),
  }))`);
  report.axe.push({ page: pageName, ...results });
  assert(`${pageName} has no axe violations`, results.violations.length === 0, `violations=${results.violations.length}`);
  return results;
};

try {
  await command('Page.enable');
  await command('Runtime.enable');
  await command('Network.enable');
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await navigate(`${origin}/login`);
  const title = await evaluate("document.querySelector('h1')?.innerText || ''");
  assert('fresh isolated Chrome reaches the sign-in form', title.includes('Welcome back'), title);
  await runAxe('Sign in');

  await evaluate("document.querySelector('#email').focus()");
  await command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
  await command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
  const tabTarget = await evaluate('document.activeElement?.id');
  assert('keyboard Tab advances from email to password', tabTarget === 'password', tabTarget);
  await command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, modifiers: 8 });
  await command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9, modifiers: 8 });
  assert('keyboard Shift+Tab returns to email', await evaluate('document.activeElement?.id') === 'email');

  const unauthenticated = await evaluate("fetch('/api/v1/auth/me', {credentials:'include'}).then(r => r.status)");
  assert('unauthenticated browser session is denied before sign-in', unauthenticated === 401, `GET /api/v1/auth/me => ${unauthenticated}`);
  const loginStatus = await evaluate(`fetch('/api/v1/auth/login', {
    method: 'POST', credentials: 'include', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({email:${JSON.stringify(email)}, password:${JSON.stringify(password)}})
  }).then(r => r.status)`);
  assert('canonical credential login authenticates the browser session', loginStatus === 200, `POST /api/v1/auth/login => ${loginStatus}`);
  await navigate(`${origin}/dashboard`);
  await waitFor("location.pathname === '/dashboard' && document.body.innerText.includes('What should you do today?')", 30000);
  const authenticated = await evaluate("fetch('/api/v1/auth/me', {credentials:'include'}).then(r => r.status)");
  assert('authenticated browser session resolves the owner through the app route', authenticated === 200, `GET /api/v1/auth/me => ${authenticated}`);
  report.pages.push({ route: '/dashboard', authenticated: true });
  await screenshot('pc-first-dashboard-disposable.png');
  await runAxe('Dashboard');

  const widths = [360, 390, 768, 1024, 1440];
  for (const width of widths) {
    await command('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false });
    const layout = await evaluate(`(() => {
      const viewport = document.documentElement.clientWidth;
      const offenders = [...document.body.querySelectorAll('*')].map(element => {
        const rect = element.getBoundingClientRect();
        return {tag: element.tagName.toLowerCase(), id: element.id, className: String(element.className || '').slice(0,80), right: Math.round(rect.right), left: Math.round(rect.left), text: (element.innerText || '').slice(0,60)};
      }).filter(item => item.right > ${width} + 2 || item.left < -2).sort((a,b) => b.right - a.right).slice(0,6);
      return {innerWidth, viewport, document: document.documentElement.scrollWidth, offenders};
    })()`);
    const pass = layout.viewport <= width + 1 && layout.document <= width + 1;
    report.viewports.push({ page: 'dashboard', width, css_viewport_width: layout.viewport, no_horizontal_overflow: pass, document_width: layout.document, overflow_examples: pass ? [] : layout.offenders });
    assert(`dashboard fits ${width}px viewport`, pass, `viewport=${layout.viewport}; document=${layout.document}; offenders=${JSON.stringify(layout.offenders)}`);
    if (width === 360 || width === 768) await screenshot(`pc-first-dashboard-${width}-disposable.png`);
  }

  const productRoute = `/products/${saved.product_id}`;
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await navigate(`${origin}/products`);
  const productListText = await evaluate('document.body.innerText');
  assert('authenticated product list displays persisted disposable catalog item', productListText.includes('[DISPOSABLE TEST] PC Persistence Sample Product'));
  report.pages.push({ route: '/products', item_visible: true });
  await runAxe('Product list');

  await navigate(`${origin}${productRoute}`);
  const productDetailText = await evaluate('document.body.innerText');
  assert('deep-linked product details display the correct persisted product', productDetailText.includes('[DISPOSABLE TEST] PC Persistence Sample Product'));
  report.pages.push({ route: productRoute, item_visible: true });
  await screenshot('pc-first-product-disposable.png');
  await runAxe('Product details');

  await navigate(`${origin}/products/${saved.product_id}/edit`);
  const editorTitle = await evaluate("document.querySelector('h1')?.innerText || ''");
  assert('product editor deep link retains the persisted product context', editorTitle === 'Edit product', editorTitle);
  await runAxe('Product editor');
  await navigate(`${origin}${productRoute}`);

  const catalogRoute = `/catalog/${saved.product_id}`;
  await navigate(`${origin}${catalogRoute}`);
  const catalogText = await evaluate('document.body.innerText');
  assert('catalog detail deep link retains product context', catalogText.includes('[DISPOSABLE TEST] PC Persistence Sample Product'));
  await screenshot('pc-first-catalog-disposable.png');
  report.pages.push({ route: catalogRoute, item_visible: true });
  await runAxe('Catalog detail');

  await evaluate('history.back()');
  const backRoute = await waitFor(`location.pathname === ${JSON.stringify(productRoute)} && document.body.innerText.includes('[DISPOSABLE TEST] PC Persistence Sample Product')`);
  assert('browser Back restores product deep link', Boolean(backRoute));
  await evaluate('history.forward()');
  await waitFor(`location.pathname === ${JSON.stringify(catalogRoute)} && document.body.innerText.includes('[DISPOSABLE TEST] PC Persistence Sample Product')`);
  assert('browser Forward restores catalog deep link', true);
  await command('Page.reload', { ignoreCache: true });
  await waitFor(`location.pathname === ${JSON.stringify(catalogRoute)} && document.body.innerText.includes('[DISPOSABLE TEST] PC Persistence Sample Product')`);
  assert('refresh retains persisted catalog context', true);

  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  report.status = 'PASS';
  report.browser_version = version.Browser;
  report.external_resources = await evaluate(`performance.getEntriesByType('resource').map(e => new URL(e.name).origin).filter(o => o !== location.origin).filter((v,i,a)=>a.indexOf(v)===i)`);
  assert('browser loaded no third-party origins', report.external_resources.length === 0, report.external_resources.join(','));
  console.log(JSON.stringify(report));
} catch (error) {
  report.status = 'FAIL';
  report.error = String(error?.stack || error).slice(0, 1600);
  try { report.current_page = await evaluate("({path: location.pathname, title: document.querySelector('h1')?.innerText || '', text: document.body.innerText.slice(0, 500)})"); } catch {}
  console.log(JSON.stringify(report));
  process.exitCode = 1;
} finally {
  try { await command('Browser.close'); } catch { socket.close(); }
}
