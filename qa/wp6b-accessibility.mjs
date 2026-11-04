// Manual evidence complements axe; it never excludes nodes or replaces engine results.
import { capture } from './seller-browser-explore.mjs';
export async function measure(run, locator, name) {
  await locator.scrollIntoViewIfNeeded();
  await locator.evaluate((e) => e.scrollIntoView({ block: 'center', inline: 'center' }));
  const v = await locator.evaluate((el) => {
    const s = getComputedStyle(el),
      rgb = (c) => c.match(/[\d.]+/g)?.map(Number);
    let bg = null,
      p = el;
    while (p) {
      const c = rgb(getComputedStyle(p).backgroundColor);
      if (c && (c[3] === undefined || c[3] === 1)) {
        bg = c;
        break;
      }
      p = p.parentElement;
    }
    const fg = rgb(s.color),
      lum = (c) =>
        c
          .slice(0, 3)
          .map((v) => {
            v /= 255;
            return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
          })
          .reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
    const r = el.getBoundingClientRect(),
      hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return {
      foreground: s.color,
      background: bg,
      ratio:
        fg && bg ? (Math.max(lum(fg), lum(bg)) + 0.05) / (Math.min(lum(fg), lum(bg)) + 0.05) : null,
      unobscured: hit === el || el.contains(hit),
      width: r.width,
      height: r.height,
      outline: s.outlineStyle,
      tag: el.tagName,
      role: el.getAttribute('role'),
      aria_label: el.getAttribute('aria-label'),
      disabled: el.disabled === true,
    };
  });
  const screenshot = await capture(run, 'manual-' + name);
  return {
    context: run.label,
    name,
    ...v,
    screenshot: screenshot.screenshot,
    status: v.ratio >= 4.5 && v.unobscured ? 'MEASURED_PASS' : 'REVIEW_REQUIRED',
  };
}
