/* POST { heard?, heard_other?, size?, invoices? } → { ok } · the questions asked while a payment is checked
   (lib/survey.ts). Signed in only; at least one answer. Answering again replaces the earlier answers. */
import { route, checkOrigin, body, json, fail } from '../../lib/server/http';
import { webSession } from '../../lib/server/auth';
import { cleanAnswers, saveAnswers } from '../../lib/server/survey';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  const s = await webSession(req);
  if (!s) return fail(401, 'signed_out');
  const answers = cleanAnswers(await body(req));
  if (!answers.length) return fail(400, 'no_answers');
  await saveAnswers(s.account_id, answers);
  return json({ ok: true });
});
