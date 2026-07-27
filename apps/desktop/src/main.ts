import { app, BrowserWindow, net, protocol, session, shell } from 'electron';
import { dirname, join, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { windowOptions } from './window-options.js';

const currentDirectory = dirname(fileURLToPath(import.meta.url));
const developmentUrl = process.env['VAYUJIT_DESKTOP_DEV_URL'];
const productionOrigin = 'app://vayujit';

protocol.registerSchemesAsPrivileged([
  {
    scheme: 'app',
    privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true },
  },
]);

async function createWindow(): Promise<void> {
  const window = new BrowserWindow(windowOptions);

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

  if (developmentUrl) {
    await window.loadURL(developmentUrl);
  } else {
    await window.loadURL(productionOrigin);
  }
}

void app
  .whenReady()
  .then(async () => {
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
