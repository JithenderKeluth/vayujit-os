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
});
