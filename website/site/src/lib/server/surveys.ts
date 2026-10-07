/* Surveys for the software (lib/surveys.ts): the panel writes one, sends it live, closes it; the software asks the
   live one on Overview (it comes with /api/app/me) and posts the answers or the X (/api/app/survey). */
import { env } from 'cloudflare:workers';
import type { SAnswer, SQuestion, Survey } from '../surveys';
import { now } from './util';

type Row = Omit<Survey, 'questions'> & { questions: string };
const parse = (r: Row): Survey => ({ ...r, questions: JSON.parse(r.questions) as SQuestion[] });

export const surveys = () =>
  env.DB.prepare(`SELECT s.*, (SELECT COUNT(*) FROM survey_replies r WHERE r.survey_id = s.id AND r.answers IS NOT NULL) AS answered,
      (SELECT COUNT(*) FROM survey_replies r WHERE r.survey_id = s.id AND r.answers IS NULL) AS closed_x
    FROM surveys s ORDER BY CASE s.state WHEN 'live' THEN 0 WHEN 'draft' THEN 1 ELSE 2 END, s.id DESC`)
    .all<Row & { answered: number; closed_x: number }>().then(r => r.results.map(x => ({ ...parse(x), answered: x.answered, closedX: x.closed_x })));

export const survey = (id: number) =>
  env.DB.prepare('SELECT * FROM surveys WHERE id = ?').bind(id).first<Row>().then(r => (r ? parse(r) : null));

/* A new survey, or a draft written again. A survey that has gone live keeps its questions, so its answers stay
   readable against them. */
export async function saveSurvey(id: number | null, title: string, questions: SQuestion[], by: string) {
  const q = JSON.stringify(questions);
  if (!id) {
    const r = await env.DB.prepare('INSERT INTO surveys (title, questions, created_at, created_by) VALUES (?, ?, ?, ?) RETURNING id')
      .bind(title, q, now(), by).first<{ id: number }>();
    return { id: r!.id };
  }
  const r = await env.DB.prepare("UPDATE surveys SET title = ?, questions = ? WHERE id = ? AND state = 'draft'").bind(title, q, id).run();
  return r.meta.changes ? { id } : { error: 'not_draft' };
}

/* Live (the software starts asking it) or closed (it stops). A closed survey isn't opened again. */
export async function setSurveyState(id: number, to: 'live' | 'closed') {
  const r = to === 'live'
    ? await env.DB.prepare("UPDATE surveys SET state = 'live', live_at = ? WHERE id = ? AND state = 'draft'").bind(now(), id).run()
    : await env.DB.prepare("UPDATE surveys SET state = 'closed', closed_at = ? WHERE id = ? AND state = 'live'").bind(now(), id).run();
  return r.meta.changes > 0;
}

/* The live survey this account hasn't answered or closed, the oldest first; what the software shows. */
export async function surveyFor(accountId: number) {
  const r = await env.DB.prepare(`SELECT * FROM surveys s WHERE s.state = 'live'
      AND NOT EXISTS (SELECT 1 FROM survey_replies r WHERE r.survey_id = s.id AND r.account_id = ?) ORDER BY s.live_at, s.id LIMIT 1`)
    .bind(accountId).first<Row>();
  if (!r) return null;
  const s = parse(r);
  return { id: s.id, title: s.title, questions: s.questions };
}

/* The answers, or the X (answers null). Only once per account and survey; only while it's live. */
export async function reply(accountId: number, id: number, answers: Record<string, SAnswer> | null) {
  const r = await env.DB.prepare(`INSERT INTO survey_replies (survey_id, account_id, answers, at)
      SELECT id, ?, ?, ? FROM surveys WHERE id = ? AND state = 'live' ON CONFLICT DO NOTHING`)
    .bind(accountId, answers ? JSON.stringify(answers) : null, now(), id).run();
  return r.meta.changes > 0;
}

/* Everything answered to one survey, with who answered (for the panel's results). */
export const replies = (id: number) =>
  env.DB.prepare(`SELECT r.answers, r.at, a.uid, a.email FROM survey_replies r JOIN accounts a ON a.id = r.account_id
      WHERE r.survey_id = ? AND r.answers IS NOT NULL ORDER BY r.at DESC`)
    .bind(id).all<{ answers: string; at: string; uid: string; email: string }>()
    .then(r => r.results.map(x => ({ ...x, answers: JSON.parse(x.answers) as Record<string, SAnswer> })));

export const closedWithX = (id: number) =>
  env.DB.prepare('SELECT COUNT(*) AS n FROM survey_replies WHERE survey_id = ? AND answers IS NULL').bind(id).first<{ n: number }>().then(r => r?.n ?? 0);
