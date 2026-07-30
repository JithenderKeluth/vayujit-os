import { describe, expect, it } from 'vitest';

import { windowOptions } from './window-options.js';

describe('windowOptions', () => {
  it('uses secure renderer defaults', () => {
    expect(windowOptions.webPreferences).toMatchObject({
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    });
  });

  it('does not expose a preload bridge or renderer privileges', () => {
    const preferences = windowOptions.webPreferences as Record<string, unknown>;
    expect(preferences['preload']).toBeUndefined();
    expect(preferences['enableRemoteModule']).toBeUndefined();
    expect(preferences['nodeIntegrationInWorker']).not.toBe(true);
    expect(preferences['nodeIntegrationInSubFrames']).not.toBe(true);
  });

  it('keeps the renderer hidden until it is ready', () => {
    expect(windowOptions.show).toBe(false);
  });

  it('keeps Campaign and calendar rendering inside the isolated Angular renderer', () => {
    const preferences = windowOptions.webPreferences as Record<string, unknown>;
    expect(preferences['webSecurity']).toBe(true);
    expect(preferences['nodeIntegration']).toBe(false);
    expect(preferences['preload']).toBeUndefined();
  });
});
