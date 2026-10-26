import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch:
    process.env.QA_PHASE === '4C'
      ? '**/phase4c.spec.mjs'
      : process.env.QA_PHASE === '4B'
        ? '**/phase4b.spec.mjs'
        : process.env.QA_PHASE === '4A'
          ? '**/phase4a.spec.mjs'
          : process.env.QA_PHASE === '4'
            ? '**/phase4.spec.mjs'
            : process.env.QA_PHASE === '3'
              ? '**/phase3*.spec.mjs'
              : process.env.QA_PHASE === '2'
                ? '**/phase2.spec.mjs'
                : '**/smoke.spec.mjs',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90000,
  expect: { timeout: 12000 },
  outputDir: process.env.QA_ARTIFACT_DIR || '../tmp/qa-agent/browser-artifacts',
  reporter: [['./reporter.mjs']],
  use: {
    baseURL: process.env.QA_ORIGIN,
    channel: 'chrome',
    headless: true,
    serviceWorkers: 'block',
    screenshot: 'only-on-failure',
    // Traces contain synthetic-session data only; kept locally, never committed.
    trace: 'retain-on-failure',
    actionTimeout: 12000,
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } },
    {
      name: 'mobile',
      use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
  ],
});
