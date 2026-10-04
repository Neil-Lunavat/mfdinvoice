/* POST { email } → { ok } · sends a sign-in code. The same for a new email (the code creates the account). */
import { route, checkOrigin, body, json } from '../../../lib/server/http';
import { normEmail, requestCode } from '../../../lib/server/auth';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  const b = await body(req);
  await requestCode(req, normEmail(b.email));
  return json({ ok: true });
});
