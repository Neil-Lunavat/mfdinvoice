import type { Plugin } from 'vite';
import { defineConfig, loadEnv } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import BRAND from '../src/client/brand.json';

/* The built window loads from disk inside WebView2, over file://. Two things break there:
   a module script (file:// has no origin, so module CORS refuses it) and `crossorigin` on the stylesheet.
   So the bundle is one classic script, and the HTML is rewritten to load it as one. */
function fromDisk(): Plugin {
  return {
    name: 'from-disk',
    apply: 'build',
    enforce: 'post',
    transformIndexHtml(html) {
      return html
        .replace(/<script type="module" crossorigin src="([^"]+)"><\/script>/, '<script defer src="$1"></script>')
        .replace(/ crossorigin(?=[ >])/g, '');
    }
  };
}

/* The name and the website's address come from the app's one copy, shared with the Python half
   (client/src/client/brand.py). */
function brand(): Plugin {
  return { name: 'brand', transformIndexHtml: html => html.replace('%NAME%', BRAND.name) };
}

/* The dev panel (src/dev/AppDevPanel.svelte) is in a checkout's window only: `uv run app` builds with VITE_DEVAPP=1
   (or `--mode devapp`) into dist-dev/. The shipped build (`bun run build` into dist/) never sets it, and
   packaging/build.py fails if the panel's marker is found in dist/. */
export default defineConfig(({ mode }) => {
  const devApp = mode === 'devapp' || loadEnv(mode, '.', 'VITE_').VITE_DEVAPP === '1';
  return {
    base: './',
    define: { __BRAND__: JSON.stringify(BRAND), 'import.meta.env.VITE_DEVAPP': JSON.stringify(devApp ? '1' : '') },
    plugins: [svelte(), fromDisk(), brand()],
    build: {
      outDir: 'dist',
      target: 'chrome110',          // WebView2 is evergreen Chromium
      modulePreload: false,
      assetsInlineLimit: 200_000,   // fonts go inside the CSS: nothing to fetch, ever
      cssCodeSplit: false,
      rollupOptions: {
        output: { format: 'iife' }
      }
    }
  };
});
