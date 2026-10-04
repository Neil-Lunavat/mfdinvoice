/* GET (Authorization: Bearer <token>) → { email, active, paid_until, source, slots, arns, app }
   app: the app's current version (consts.ts APP). An app older than it must update before it does anything else. */
import { route, json, fail } from '../../../lib/server/http';
import { appSession } from '../../../lib/server/auth';
import { licence } from '../../../lib/server/account';
import { APP } from '../../../consts';
export const prerender = false;

export const GET = route(async req => {
  const s = await appSession(req);
  if (!s) return fail(401, 'bad_token');
  return json({ email: s.email, ...(await licence(s.account_id)), app: APP });
});
