/* POST (Authorization: Bearer <token>) → { ok }. Ends that token. */
import { route, checkOrigin, json } from '../../../lib/server/http';
import { bearer, endSession } from '../../../lib/server/auth';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req, true);
  await endSession(bearer(req));
  return json({ ok: true });
});
