/* POST {} → { ok } · ends this browser's session. */
import { route, checkOrigin, json, cookie } from '../../../lib/server/http';
import { endSession, clearCookies, withCookies } from '../../../lib/server/auth';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  await endSession(cookie(req, 'sid'));
  return withCookies(json({ ok: true }), clearCookies());
});
