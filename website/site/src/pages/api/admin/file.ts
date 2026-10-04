/* GET ?key=proofs/… | support/… → a payment screenshot or a support screenshot, from R2. */
import { env } from 'cloudflare:workers';
import { fail } from '../../../lib/server/http';
import { gated } from '../../../lib/server/admin';
export const prerender = false;

export const GET = gated('control', async (_req, url) => {
  const key = url.searchParams.get('key') || '';
  if (!/^(proofs|support)\/[A-Za-z0-9._-]{1,80}$/.test(key)) return fail(404, 'not_found');
  const obj = await env.FILES.get(key);
  if (!obj) return fail(404, 'not_found');
  return new Response(obj.body, { headers: { 'content-type': obj.httpMetadata?.contentType || 'application/octet-stream', 'cache-control': 'private, max-age=3600' } });
});
