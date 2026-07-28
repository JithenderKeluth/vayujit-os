import { app, BrowserWindow, net, protocol, session, shell } from 'electron';
import { dirname, join, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { windowOptions } from './window-options.js';

const currentDirectory = dirname(fileURLToPath(import.meta.url));
const developmentUrl = process.env['VAYUJIT_DESKTOP_DEV_URL'];
const smokeMode = process.env['VAYUJIT_DESKTOP_SMOKE'] === '1';
const productionOrigin = 'app://vayujit';

protocol.registerSchemesAsPrivileged([
  {
    scheme: 'app',
    privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true },
  },
]);

async function createWindow(): Promise<void> {
  const window = new BrowserWindow(windowOptions);
  console.info(
    `[desktop] BrowserWindow created (sandbox=${String(windowOptions.webPreferences?.sandbox)})`,
  );

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) {
      void shell.openExternal(url);
    }
    return { action: 'deny' };
  });
  window.webContents.on('will-navigate', (event, url) => {
    const allowed = developmentUrl
      ? url.startsWith(developmentUrl)
      : url.startsWith(productionOrigin);
    if (!allowed) event.preventDefault();
  });
  window.once('ready-to-show', () => window.show());

  const rendererUrl = developmentUrl ?? productionOrigin;
  const smokeTimeout = smokeMode
    ? setTimeout(() => {
        console.error('[desktop] Smoke test timed out before renderer readiness.');
        app.exit(1);
      }, 20_000)
    : undefined;
  try {
    await window.loadURL(rendererUrl);
    const rendererReady: unknown = await window.webContents.executeJavaScript(
      "document.readyState === 'complete' && Boolean(document.querySelector('app-root'))",
    );
    if (rendererReady !== true) {
      throw new Error('Renderer did not expose a ready application root.');
    }
    console.info(`[desktop] Renderer ready: ${rendererUrl}`);
    if (smokeMode) {
      if (smokeTimeout) clearTimeout(smokeTimeout);
      console.info('[desktop] Smoke test passed.');
      app.exit(0);
    }
  } catch (error) {
    if (smokeTimeout) clearTimeout(smokeTimeout);
    console.error(`[desktop] Renderer failed to load: ${rendererUrl}`, error);
    if (smokeMode) app.exit(1);
    throw error;
  }
}

void app
  .whenReady()
  .then(async () => {
    console.info(`[desktop] Electron ${process.versions.electron} ready.`);
    if (!developmentUrl) {
      const webRoot = join(currentDirectory, '../../../dist/apps/web/browser');
      protocol.handle('app', (request) => {
        const pathname = new URL(request.url).pathname;
        const requestedFile = pathname === '/' ? 'index.html' : pathname.slice(1);
        const assetPath = requestedFile.includes('.') ? requestedFile : 'index.html';
        const resolvedPath = resolve(webRoot, assetPath);
        if (!resolvedPath.startsWith(`${resolve(webRoot)}${sep}`)) {
          return new Response('Not found', { status: 404 });
        }
        return net.fetch(pathToFileURL(resolvedPath).toString());
      });
    }
    session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => {
      callback(false);
    });
    await createWindow();

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) void createWindow();
    });
  })
  .catch((error) => {
    console.error('Failed to initialize desktop application.', error);
    app.quit();
  });

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
