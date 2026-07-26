import { app, BrowserWindow, session, shell } from 'electron';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { windowOptions } from './window-options.js';

const currentDirectory = dirname(fileURLToPath(import.meta.url));
const developmentUrl = process.env['VAYUJIT_DESKTOP_DEV_URL'];

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
      : url.startsWith('file:');
    if (!allowed) event.preventDefault();
  });
  window.once('ready-to-show', () => window.show());

  if (developmentUrl) {
    await window.loadURL(developmentUrl);
  } else {
    await window.loadFile(join(currentDirectory, '../../../dist/apps/web/browser/index.html'));
  }
}

app.whenReady().then(async () => {
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => {
    callback(false);
  });
  await createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) void createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
