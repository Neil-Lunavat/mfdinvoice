/* The app's sign-in, step 2. POST { email, code, version?, device?, replace? } → { token, email }. The token lasts a year
   from its last use. version (the software's) and device (the PC's name) are optional: they go in the account's activity,
   and device is kept on the session. One PC per account: when the account is already signed in on a PC and replace is not
   true, the answer is 409 other_pc { device, last_seen } (device may be null) once the code is right, and the code is NOT
   used up: the same code is sent again with replace: true, which signs the other PC out (its token then answers 401
   signed_in_elsewhere). An account whose deletion is pending is refused: 409 pending_deletion { delete_after } (the
   website keeps it). */
import { env } from 'cloudflare:workers';
import { route, checkOrigin, body, json, fail, str } from '../../../lib/server/http';
import { event } from '../../../lib/server/events';
import { normEmail, verifyCode, checkCode, newSession, liveAppSessions, endAppSessions, APP_LIFE } from '../../../lib/server/auth';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req, true);
  const b = await body(req);
  const email = normEmail(b.email);
  const version = str(b.version, 20), device = str(b.device, 60);
  if (b.replace !== true) {
    /* a live session on another PC, for an account not being deleted: ask, with the code checked but kept */
    const acc = await env.DB.prepare('SELECT id, delete_after FROM accounts WHERE email = ?').bind(email).first<{ id: number; delete_after: string | null }>();
    const live = acc && !acc.delete_after ? (await liveAppSessions(acc.id))[0] : null;
    /* the same PC signing in again (reinstalled, its data wiped) isn't asked about itself */
    if (live && !(device && live.device === device)) {
      await checkCode(req, email, b.code);
      return fail(409, 'other_pc', { device: live.device, last_seen: live.last_seen });
    }
  }
  const a = await verifyCode(req, email, b.code);
  if (a.delete_after) return fail(409, 'pending_deletion', { delete_after: a.delete_after });
  const replaced = await liveAppSessions(a.id);
  if (replaced.length) await endAppSessions(a.id, device);
  const token = await newSession(a.id, 'app', APP_LIFE, device);
  const out = replaced.length ? `signed ${replaced[0].device ?? 'another PC'} out` : null;
  await event('buyer', 'signin.app', a.id, null, [version && `v${version}`, device, out].filter(Boolean).join(' · ') || null).run();
  return json({ token, email });
});
