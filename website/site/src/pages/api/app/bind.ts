/* POST (Authorization: Bearer <token>) { arn, holder } → { ok, arn, already, slots, used, trial_until? }
   Binds an ARN to the signed-in account (lib/server/bind.ts): the app calls it when setup finishes on an account
   with a plan, and when the person presses Activate free trial on one that has never had a plan. */
import { route, body, fail, checkOrigin } from '../../../lib/server/http';
import { appSession } from '../../../lib/server/auth';
import { bindArn } from '../../../lib/server/bind';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req, true);
  const s = await appSession(req);
  if (!s) return fail(401, 'bad_token');
  const b = await body(req);
  return bindArn(s.account_id, b.arn, b.holder);
});
