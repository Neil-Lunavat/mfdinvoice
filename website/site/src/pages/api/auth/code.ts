/* POST { email, turnstile? } → { ok } · sends a sign-in code. The same for a new email (the code creates the account). */
import { route, checkOrigin, body, json, fail } from '../../../lib/server/http';
import { normEmail, requestCode } from '../../../lib/server/auth';
import { turnstileOk } from '../../../lib/server/turnstile';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  const b = await body(req);
  /* the Turnstile check, when it is switched on */
  if (!(await turnstileOk(req, b.turnstile))) return fail(403, 'challenge');
  await requestCode(req, normEmail(b.email));
  return json({ ok: true });
});
