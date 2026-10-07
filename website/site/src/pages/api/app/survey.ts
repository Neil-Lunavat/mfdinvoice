/* POST (Authorization: Bearer <token>) { id, answers: { <key>: { picked: [text], text } } } → { ok }
   POST … { id, closed: true } → { ok } · the X on the software's toast: that survey is never asked again.
   Once per account and survey, and only while it's live (409 not_open otherwise). */
import { route, checkOrigin, body, json, fail } from '../../../lib/server/http';
import { appSession } from '../../../lib/server/auth';
import { reply, survey } from '../../../lib/server/surveys';
import { cleanReply } from '../../../lib/surveys';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req, true);
  const s = await appSession(req);
  if (!s) return fail(401, 'bad_token');
  const b = await body(req);
  const sv = await survey(Number(b.id) || 0);
  if (!sv || sv.state !== 'live') return fail(409, 'not_open');
  if (b.closed === true) return (await reply(s.account_id, sv.id, null)) ? json({ ok: true }) : fail(409, 'not_open');
  const answers = cleanReply(sv.questions, b.answers);
  if (!Object.keys(answers).length) return fail(400, 'no_answers');
  return (await reply(s.account_id, sv.id, answers)) ? json({ ok: true }) : fail(409, 'not_open');
});
