/* in-page links glide to their place instead of jumping (0.6 to 1.2 s, eased; off with reduced motion) */
const ease = (t: number) => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const page = (p: string) => p.replace(/index\.html$/, '');
document.addEventListener('click', e => {
  const a = (e.target as Element).closest?.('a[href*="#"]') as HTMLAnchorElement | null;
  if (!a || e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey) return;
  const u = new URL(a.href, location.href);
  if (page(u.pathname) !== page(location.pathname) || u.hash.length < 2) return;
  const el = document.getElementById(decodeURIComponent(u.hash.slice(1)));
  if (!el) return;
  e.preventDefault();
  history.pushState(null, '', u.hash);
  const to = Math.max(0, el.getBoundingClientRect().top + scrollY - (parseFloat(getComputedStyle(el).scrollMarginTop) || 0));
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return scrollTo({ top: to, behavior: 'instant' });
  const from = scrollY, d = to - from, ms = Math.min(1200, 600 + Math.abs(d) * .15), t0 = performance.now();
  const step = (now: number) => { const k = Math.min(1, (now - t0) / ms); scrollTo({ top: from + d * ease(k), behavior: 'instant' }); if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
});
