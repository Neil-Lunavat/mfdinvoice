/* GET → a blog image from R2 (blog/<name>), for the public blog and the editor. */
import { env } from 'cloudflare:workers';
import { route, fail } from '../../../lib/server/http';
export const prerender = false;

export const GET = route(async (_req, url) => {
  const name = url.pathname.split('/').pop() || '';
  if (!/^[A-Za-z0-9._-]{1,80}$/.test(name)) return fail(404, 'not_found');
  const obj = await env.FILES.get(`blog/${name}`);
  if (!obj) return fail(404, 'not_found');
  return new Response(obj.body, { headers: { 'content-type': obj.httpMetadata?.contentType || 'application/octet-stream', 'cache-control': 'public, max-age=31536000, immutable', etag: obj.httpEtag } });
});
