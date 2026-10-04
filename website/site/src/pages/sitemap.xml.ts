/* The sitemap: the public pages and every published blog post (from the database, so it's a server route). */
import { SITE_URL } from '../consts';
import { listPosts } from '../lib/server/blog';
export const prerender = false;

/* the public pages, from the files in src/pages (not the pages that only make sense inside the buying path) */
const PRIVATE = ['/404', '/signin', '/account', '/checkout'];
const pages = Object.keys(import.meta.glob('./*.astro'))
  .map(f => '/' + f.slice(2, -6).replace(/^index$/, ''))
  .filter(p => !PRIVATE.includes(p));

export async function GET(ctx: any) {
  ctx.cache?.set?.({ maxAge: 3600, tags: ['blog'] });
  const posts = await listPosts();
  const url = (p: string, mod?: string) => `<url><loc>${new URL(p, SITE_URL).href.replace(/\/$/, p === '/' ? '/' : '')}</loc>${mod ? `<lastmod>${mod.slice(0, 10)}</lastmod>` : ''}</url>`;
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${[
    ...pages.map(p => url(p)), url('/blog'), ...posts.map(p => url(p.path, p.updated_at)),
  ].join('\n')}\n</urlset>\n`;
  return new Response(xml, { headers: { 'content-type': 'application/xml; charset=utf-8' } });
}
