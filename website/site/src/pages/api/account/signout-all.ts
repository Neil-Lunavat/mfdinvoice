/* POST → { ok } · "Sign out of all devices": ends every session of the account (the website's and the app's), this
   one too. */
import { env } from 'cloudflare:workers';
import { route, checkOrigin, json, fail } from '../../../lib/server/http';
import { webSession, clearCookies, withCookies } from '../../../lib/server/auth';
import { event } from '../../../lib/server/events';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  const s = await webSession(req);
  if (!s) return fail(401, 'signed_out');
  await env.DB.batch([
    env.DB.prepare('DELETE FROM sessions WHERE account_id = ?').bind(s.account_id),
    event('buyer', 'signout.everywhere', s.account_id),
  ]);
  return withCookies(json({ ok: true }), clearCookies());
});
