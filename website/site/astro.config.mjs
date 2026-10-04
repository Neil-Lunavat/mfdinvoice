// @ts-check
import { defineConfig } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';
import { cacheCloudflare } from '@astrojs/cloudflare/cache';
import { SITE_URL } from './src/consts';

export default defineConfig({
  site: SITE_URL,
  /* Every page is prerendered to HTML. A server route (the backend, the blog, the admin panel, the editor) opts out
     with `export const prerender = false`, and runs on the Worker. The sitemap is a server route (/sitemap.xml),
     because the blog's posts come from the database. */
  output: 'static',
  /* No images to resize and no sessions, so the Worker needs no Images or KV binding. */
  adapter: cloudflare({ imageService: 'passthrough' }),
  session: false,
  /* The blog's pages are cached at Cloudflare's edge (Astro.cache, tag 'blog'); publishing purges the tag. */
  cache: { provider: cacheCloudflare() },
  /* /pricing, not /pricing/ (pages are built as pricing.html) */
  trailingSlash: 'never',
  /* keep the markup's whitespace as written: compressing it drops the space between a line's text and a tag on the next line */
  compressHTML: false,
  build: { format: 'file' },
  vite: {
    build: {
      /* Lightning CSS (Vite's default CSS minifier) drops the unprefixed backdrop-filter on the nav;
         esbuild minifies without rewriting declarations. */
      cssMinify: 'esbuild',
      /* every script is a file of its own, never inlined: the Content-Security-Policy allows only our own scripts */
      assetsInlineLimit: 0,
    },
  },
});
