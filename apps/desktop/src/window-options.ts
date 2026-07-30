import type { BrowserWindowConstructorOptions } from 'electron';

export const windowOptions: BrowserWindowConstructorOptions = {
  width: 1280,
  height: 800,
  minWidth: 900,
  minHeight: 600,
  show: false,
  webPreferences: {
    contextIsolation: true,
    nodeIntegration: false,
    sandbox: true,
    webSecurity: true,
  },
};
