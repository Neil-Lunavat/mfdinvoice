/* POST { action: "approve" | "reject" | "unblock", ref, note?, tell? } → { ok, invoice? } · a UPI payment, checked by hand
   (upi.ts). reject: note is the reason, emailed to the buyer only if tell. unblock: they're emailed only if tell. */
import { json, fail, body, str } from '../../../lib/server/http';
import { gated } from '../../../lib/server/admin';
import { approve, reject, unblock } from '../../../lib/server/upi';
export const prerender = false;

export const POST = gated('control', async (req, _url, me) => {
  const b = await body(req);
  const ref = str(b.ref, 20).toUpperCase();
  const r = b.action === 'approve' ? await approve(ref, me.email)
    : b.action === 'reject' ? await reject(ref, str(b.note, 500), b.tell === true, me.email)
    : b.action === 'unblock' ? await unblock(ref, me.email, b.tell === true)
    : { error: 'bad_action' };
  return 'error' in r ? fail(400, r.error as string, r) : json(r);
});
