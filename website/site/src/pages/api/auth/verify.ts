/* POST { email, code, keep } → { ok, email, delete_after?, delete_on?, gift_until?, gift_until_text?, gift_revoked?, was_deleted? } and the session cookies.
   was_deleted: 'self' or 'admin', when this email's old account was deleted and this sign-in made a new one.
   keep: 30 days; otherwise until the browser closes (1 day at most). If the account's deletion is pending, the page
   asks whether to keep it (POST /api/account/keep) or sign out; until then the session opens nothing else. */
import { route, checkOrigin, body, json } from '../../../lib/server/http';
import { normEmail, verifyCode, newSession, sessionCookies, withCookies, setupCookie, planCookie, WEB_KEEP, WEB_SHORT } from '../../../lib/server/auth';
import { getAccount, getPlan } from '../../../lib/server/account';
import { event } from '../../../lib/server/events';
import { istWhen } from '../../../lib/server/util';
import { longDate } from '../../../lib/invoice';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  const b = await body(req);
  const email = normEmail(b.email), keep = b.keep !== false;
  const a = await verifyCode(req, email, b.code);
  const t = await newSession(a.id, 'web', keep ? WEB_KEEP : WEB_SHORT);
  await event('buyer', 'signin.web', a.id).run();
  const pending = a.delete_after ? { delete_after: a.delete_after, delete_on: istWhen(a.delete_after) } : {};
  /* a gift that started with this sign-in: the page shows it */
  const gift = a.gift_until ? { gift_until: a.gift_until, gift_until_text: longDate(a.gift_until) } : a.gift_revoked ? { gift_revoked: true } : {};
  const gone = a.deleted_by ? { was_deleted: a.deleted_by === 'buyer' ? 'self' : 'admin' } : {};
  const [acct, plan] = await Promise.all([getAccount(a.id), getPlan(a.id)]);
  return withCookies(json({ ok: true, email, ...pending, ...gift, ...gone }), [...sessionCookies(t, keep), setupCookie(!acct?.bill_name || !acct?.bill_address), planCookie(!!plan)]);
});
