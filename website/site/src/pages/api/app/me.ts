/* GET (Authorization: Bearer <token>) → { email, active, paid_until, source, slots, arns, trial_used, app, survey }
   app: the app's current version (consts.ts APP). An app older than it must update before it does anything else.
   survey: the live survey this account hasn't answered or closed ({ id, title, questions }), or null. */
import { route, json, fail } from '../../../lib/server/http';
import { appSession } from '../../../lib/server/auth';
import { licence } from '../../../lib/server/account';
import { surveyFor } from '../../../lib/server/surveys';
import { APP } from '../../../consts';
export const prerender = false;

export const GET = route(async req => {
  const s = await appSession(req);
  if (!s) return fail(401, 'bad_token');
  const [lic, survey] = await Promise.all([licence(s.account_id), surveyFor(s.account_id)]);
  return json({ email: s.email, ...lic, app: APP, survey });
});
