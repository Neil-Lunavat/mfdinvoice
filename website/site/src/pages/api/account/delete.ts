/* POST { confirm: "DELETE MY ACCOUNT" } → { ok } · schedules the deletion a day from now, ends every session and signs
   out. Signing in before then offers to keep the account; the daily job deletes it. Receipts and payments stay.
   Refused (409 payment_in_review) while a payment is waiting to be checked: it would have no account to go to. */
import { route, checkOrigin, body, json, fail } from '../../../lib/server/http';
import { webSession, clearCookies, withCookies } from '../../../lib/server/auth';
import { scheduleDeletion } from '../../../lib/server/account';
import { openUpiOrder } from '../../../lib/server/upi';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  const s = await webSession(req);
  if (!s) return fail(401, 'signed_out');
  const b = await body(req);
  if (b.confirm !== 'DELETE MY ACCOUNT') return fail(400, 'not_confirmed');
  if ((await openUpiOrder(s.account_id))?.status === 'review') return fail(409, 'payment_in_review');
  await scheduleDeletion(s.account_id, s.email);
  return withCookies(json({ ok: true }), clearCookies());
});
