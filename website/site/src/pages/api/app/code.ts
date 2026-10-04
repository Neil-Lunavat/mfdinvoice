/* The app's sign-in, step 1. POST { email } → { ok }. Same rules as the site's, but the app never makes an account:
   an email with none is refused (no_account), and the person signs up on the website. */
import { env } from 'cloudflare:workers';
import { route, checkOrigin, body, json, fail, HttpError } from '../../../lib/server/http';
import { normEmail, requestCode } from '../../../lib/server/auth';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req, true);
  const b = await body(req);
  const email = normEmail(b.email);
  if (!(await env.DB.prepare('SELECT 1 FROM accounts WHERE email = ?').bind(email).first())) throw new HttpError(fail(404, 'no_account'));
  await requestCode(req, email);
  return json({ ok: true });
});
