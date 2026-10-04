/* POST { action, account, ... } → { ok } · the fixes on an account's page:
   free_arn { arn, tell? } · change_email { email } · resend { number } · cancel_deletion · gift.
   POST { action: "delete", accounts: [id, …] } → { ok, deleted } · deletes those accounts now (the Accounts list). */
import { json, fail, body, str } from '../../../lib/server/http';
import { gated } from '../../../lib/server/admin';
import { freeArn, changeEmail, cancelDeletion, getAccount, deleteAccount } from '../../../lib/server/account';
import { resendReceipt } from '../../../lib/server/orders';
import { giveGift } from '../../../lib/server/gifts';
import { normArn } from '../../../lib/server/arn';
import { cleanEmail, now } from '../../../lib/server/util';
export const prerender = false;

export const POST = gated('control', async (req, _url, me) => {
  const b = await body(req);
  if (b.action === 'delete') {
    const ids = Array.isArray(b.accounts) ? [...new Set(b.accounts.map(Number).filter(Number.isInteger))].slice(0, 100) as number[] : [];
    if (!ids.length) return fail(400, 'no_accounts');
    let deleted = 0;
    for (const x of ids) {
      const a = await getAccount(x);
      if (a) { await deleteAccount(a.id, a.email, now(), me.email); deleted++; }
    }
    return json({ ok: true, deleted });
  }
  const id = Number(b.account);
  const a = Number.isInteger(id) ? await getAccount(id) : null;
  if (!a) return fail(404, 'no_account');
  let r: { ok?: boolean; error?: string; [k: string]: unknown };
  switch (b.action) {
    case 'free_arn': {
      const arn = normArn(b.arn);
      r = !arn ? { error: 'bad_arn' } : await freeArn(id, arn, me.email, b.tell === true);
      break;
    }
    case 'change_email': {
      const email = cleanEmail(str(b.email, 254));
      r = !email ? { error: 'bad_email' } : await changeEmail(id, email, me.email);
      break;
    }
    case 'resend':
      r = await resendReceipt(str(b.number, 30), me.email);
      break;
    case 'cancel_deletion':
      r = (await cancelDeletion(id, me.email)) ? { ok: true } : { error: 'not_pending' };
      break;
    case 'gift':
      { const g = await giveGift(a.email, me.email); r = 'error' in g ? g : { ok: true, ...g }; }
      break;
    default:
      r = { error: 'bad_action' };
  }
  return r.error ? fail(400, r.error, r) : json(r);
});
