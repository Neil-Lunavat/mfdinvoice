/* POST { action: 'save', id?, title, questions } → { ok, id } · a new survey, or a draft written again
   POST { action: 'live' | 'close', id } → { ok } · the software starts asking it, or stops (lib/server/surveys.ts) */
import { json, fail, body, str } from '../../../lib/server/http';
import { gated } from '../../../lib/server/admin';
import { event } from '../../../lib/server/events';
import { saveSurvey, setSurveyState } from '../../../lib/server/surveys';
import { cleanQuestions, LIMITS } from '../../../lib/surveys';
export const prerender = false;

export const POST = gated('control', async (req, _url, me) => {
  const b = await body(req);
  const id = Number(b.id) || null;
  if (b.action === 'save') {
    const title = str(b.title, LIMITS.title);
    if (!title) return fail(400, 'no_title');
    const questions = cleanQuestions(b.questions);
    if (typeof questions === 'string') return fail(400, questions);
    const r = await saveSurvey(id, title, questions, me.email);
    if ('error' in r) return fail(409, r.error!);
    await event(me.email, 'survey.saved', null, String(r.id));
    return json({ ok: true, id: r.id });
  }
  if ((b.action === 'live' || b.action === 'close') && id) {
    if (!(await setSurveyState(id, b.action === 'live' ? 'live' : 'closed'))) return fail(409, 'wrong_state');
    await event(me.email, b.action === 'live' ? 'survey.live' : 'survey.closed', null, String(id));
    return json({ ok: true });
  }
  return fail(400, 'bad_action');
});
