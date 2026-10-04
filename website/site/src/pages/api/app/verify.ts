/* The app's sign-in, step 2. POST { email, code, version?, device? } → { token, email }. The token lasts a year from
   its last use. version (the app's) and device (the PC's name) are optional: they go in the account's activity.
   An account whose deletion is pending is refused: 409 pending_deletion { delete_after } (the website keeps it). */
import { route, checkOrigin, body, json, fail, str } from '../../../lib/server/http';
import { event } from '../../../lib/server/events';
import { normEmail, verifyCode, newSession, APP_LIFE } from '../../../lib/server/auth';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req, true);
  const b = await body(req);
  const email = normEmail(b.email);
  const a = await verifyCode(req, email, b.code);
  if (a.delete_after) return fail(409, 'pending_deletion', { delete_after: a.delete_after });
  const token = await newSession(a.id, 'app', APP_LIFE);
  const version = str(b.version, 20), device = str(b.device, 60);
  await event('buyer', 'signin.app', a.id, null, [version && `v${version}`, device].filter(Boolean).join(' · ') || null).run();
  return json({ token, email });
});
