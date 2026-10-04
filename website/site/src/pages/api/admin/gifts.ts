/* POST { action: "give", email } → { ok, id, started, until } · { action: "revoke", id } → { ok } */
import { json, fail, body, str } from '../../../lib/server/http';
import { gated } from '../../../lib/server/admin';
import { giveGift, revokeGift } from '../../../lib/server/gifts';
import { cleanEmail } from '../../../lib/server/util';
export const prerender = false;

export const POST = gated('control', async (req, _url, me) => {
  const b = await body(req);
  if (b.action === 'give') {
    const email = cleanEmail(str(b.email, 254));
    if (!email) return fail(400, 'bad_email');
    const r = await giveGift(email, me.email);
    return 'error' in r ? fail(400, r.error!) : json({ ok: true, ...r });
  }
  if (b.action === 'revoke') {
    const r = await revokeGift(Number(b.id), me.email);
    return 'error' in r ? fail(400, r.error!) : json(r);
  }
  return fail(400, 'bad_action');
});
