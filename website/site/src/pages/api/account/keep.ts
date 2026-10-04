/* POST {} → { ok, gift_until? } · "Keep my account": signed in during the day before a deletion, this cancels it. */
import { route, checkOrigin, json, fail } from '../../../lib/server/http';
import { pendingSession } from '../../../lib/server/auth';
import { cancelDeletion } from '../../../lib/server/account';
import { applyGift } from '../../../lib/server/gifts';
import { longDate } from '../../../lib/invoice';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  const s = await pendingSession(req);
  if (!s) return fail(401, 'signed_out');
  await cancelDeletion(s.account_id, 'buyer');
  /* a gift that waited while the deletion was pending starts now */
  const until = await applyGift(s.account_id, s.email);
  return json({ ok: true, ...(until ? { gift_until: until, gift_until_text: longDate(until) } : {}) });
});
