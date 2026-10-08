import type { APIRoute } from 'astro';
import { INDEXING, SITE_URL } from '../consts';

/* While INDEXING is false nothing is crawled. */
export const GET: APIRoute = () => new Response(
  INDEXING
    ? `User-agent: *\nAllow: /\n\nSitemap: ${new URL('/sitemap.xml', SITE_URL).href}\n`
    : 'User-agent: *\nDisallow: /\n',
  { headers: { 'Content-Type': 'text/plain; charset=utf-8' } },
);
