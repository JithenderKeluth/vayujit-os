import {
  test,
  expect,
  login,
  manifest,
  scanAxe,
  attach,
  inspectContrastNode,
} from '../explore.mjs';

test('QA-P4A-01 named controls accurate progress and one application main', async ({
  page,
}, info) => {
  await login(page);
  await page.goto('/ai/history');
  for (const name of ['Request status', 'Review status', 'Date from', 'Date to'])
    await expect(page.getByLabel(name, { exact: true })).toBeVisible();
  await page.getByLabel('Request status', { exact: true }).focus();
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Review status', { exact: true })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByLabel('Request status', { exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('columnheader', { name: 'Actions', exact: true })).toBeVisible();
  expect((await scanAxe(page, info, 'named-history-controls')).violations).toEqual([]);
  const { phase2: selected } = await manifest();
  for (const route of [
    '/ai/video',
    '/ai/generate',
    '/ads/accounts',
    '/intelligence/product-opportunities',
    '/intelligence/trends',
    `/intelligence/product-opportunities/${selected.opportunity_id}`,
  ]) {
    await page.goto(route);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('main')).toHaveCount(1);
    expect(
      (await scanAxe(page, info, 'semantics-' + route.replaceAll('/', '-'))).violations,
    ).toEqual([]);
  }
  await page.goto('/ai/video');
  const progress = page.getByRole('progressbar', { name: 'Generate workflow progress' });
  await expect(progress).toHaveAttribute('aria-valuenow', '1');
  await expect(progress).toHaveAttribute('aria-valuemax', '14');
  await attach(info, 'semantics-assertions', {
    labels: 4,
    application_main_count: 1,
    progress: 'Canonical step value; no workflow execution or provider call',
  });
});

test('QA-P4A-02 named overflow regions scroll with keys and release focus', async ({
  page,
}, info) => {
  test.setTimeout(600000);
  await login(page);
  const cases = [
    ['/ads/accounts', '.table-scroll'],
    ['/ads/campaigns', '.table-scroll'],
    ['/ads/analytics', '.table-scroll'],
    ['/ads/calendar', '.table-scroll'],
    ['/ads/recovery', '.table-scroll'],
    ['/ai/video', '.table-wrap'],
    ['/intelligence/websites', '.table-wrap'],
    ['/intelligence/external', '.table-wrap'],
    ['/marketplaces/video', '.marketplace-table'],
    ['/marketplaces/meesho', '.marketplace-table'],
    ['/social', '.table-wrap'],
    ['/social/settings', '.table-wrap'],
  ];
  const results = [];
  for (const [route, selector] of cases) {
    await page.goto(route);
    await page.waitForLoadState('networkidle');
    const regions = page.locator(selector);
    expect(await regions.count()).toBeGreaterThan(0);
    for (let i = 0; i < (await regions.count()); i++) {
      const region = regions.nth(i);
      await region.scrollIntoViewIfNeeded();
      await expect(region).toHaveAttribute('tabindex', '0');
      expect(
        (await region.getAttribute('aria-label')) || (await region.getAttribute('aria-labelledby')),
      ).toBeTruthy();
      await region.focus();
      await expect(region).toBeFocused();
      await region.evaluate((e) => e.scrollTo({ left: 0, behavior: 'instant' }));
      const geometry = await region.evaluate((e) => ({
        scroll: e.scrollWidth,
        client: e.clientWidth,
      }));
      if (geometry.scroll > geometry.client + 1) {
        await page.keyboard.press('ArrowRight');
        await expect.poll(() => region.evaluate((e) => e.scrollLeft)).toBeGreaterThan(0);
      }
      const outline = await region.evaluate((e) => ({
        style: getComputedStyle(e).outlineStyle,
        width: getComputedStyle(e).outlineWidth,
      }));
      expect(outline.style).not.toBe('none');
      expect(parseFloat(outline.width)).toBeGreaterThanOrEqual(2);
      await page.keyboard.press('Tab');
      await expect(region).not.toBeFocused();
      results.push({
        route,
        index: i,
        keyboard_scroll: geometry.scroll > geometry.client + 1,
        outline,
        focus_released: true,
      });
    }
    const scan = await scanAxe(page, info, 'keyboard-' + route.replaceAll('/', '-'));
    expect.soft(scan.violations).toEqual([]);
  }
  await attach(info, 'keyboard-region-results', results);
});

test('QA-P4A-03 all six captions remain readable across supported widths', async ({
  page,
}, info) => {
  test.setTimeout(600000);
  await login(page);
  const { phase2: p } = await manifest();
  const states = [
    [
      'due',
      `/intelligence/due-diligence?opportunity_id=${p.opportunity_id}&supplier_id=${p.supplier_id}`,
      1,
    ],
    ['economics', `/intelligence/sourcing-economics?opportunity_id=${p.opportunity_id}`, 2],
    ['stale', `/intelligence/sourcing-economics?opportunity_id=${p.stale_opportunity_id}`, 1],
    [
      'decision',
      `/intelligence/sourcing-economics?opportunity_id=${p.opportunity_id}&journey_id=${p.goal_id}`,
      2,
    ],
  ];
  for (const width of [360, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: width >= 1024 ? 1000 : 844 });
    for (const [state, route, count] of states) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      await scanAxe(page, info, `caption-document-${state}-${width}`);
      const captions = page.locator('caption');
      await expect(captions).toHaveCount(count);
      for (let i = 0; i < count; i++) {
        const result = await inspectContrastNode(
          page,
          info,
          captions.nth(i),
          `${state}-${i}-${width}`,
        );
        expect
          .soft(result.text_horizontally_in_view, `${state} caption ${i} readable at ${width}`)
          .toBe(true);
        expect.soft(result.violations).toEqual([]);
        expect.soft(result.incomplete).toEqual([]);
        expect.soft(result.passes).toContain('color-contrast');
        const clip = await captions.nth(i).evaluate((e) => {
          const owner = e.closest('[tabindex="0"]');
          const r = owner.getBoundingClientRect();
          const range = document.createRange();
          range.selectNodeContents(e);
          return [...range.getClientRects()].every(
            (b) =>
              b.left >= r.left - 1 &&
              b.right <= r.right + 1 &&
              b.top >= r.top - 1 &&
              b.bottom <= r.bottom + 1,
          );
        });
        expect.soft(clip, 'Caption text fits its actual scroll-container clip').toBe(true);
      }
    }
  }
  // The full website scan retains unrelated obscured table cells as incomplete.
  // Expose the two original failing small-text selectors independently; do not
  // suppress any full-document or targeted axe rule.
  await page.setViewportSize({ width: info.project.name === 'mobile' ? 390 : 1440, height: 1000 });
  await page.goto('/intelligence/websites');
  await page.waitForLoadState('networkidle');
  await scanAxe(page, info, 'original-website-state-text');
  for (const state of ['state-high', 'state-expired']) {
    const targets = page.locator(`.${state} > small`);
    expect(await targets.count()).toBeGreaterThan(0);
    for (let i = 0; i < (await targets.count()); i++) {
      const node = await inspectContrastNode(
        page,
        info,
        targets.nth(i),
        `state-contrast-${state}-${i}`,
      );
      expect(node.text_horizontally_in_view).toBe(true);
      expect(node.violations).toEqual([]);
      expect(node.incomplete).toEqual([]);
      expect(node.passes).toContain('color-contrast');
    }
  }
});
