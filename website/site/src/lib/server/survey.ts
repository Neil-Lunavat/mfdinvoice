/* Survey answers (the `answers` table): saving an account's answers, reading them back, and the counts for the panel. */
import { env } from 'cloudflare:workers';
import { SURVEY, QUESTIONS } from '../survey';
import { now } from './util';
import { str } from './http';

/* Checks the posted answers against the questions. Unknown questions and options are dropped. */
export function cleanAnswers(b: Record<string, unknown>) {
  const out: [string, string][] = [];
  for (const q of QUESTIONS) {
    const a = str(b[q.key], 40);
    if (!q.options.some(o => o[0] === a)) continue;
    out.push([q.key, a]);
    if (q.other && a === q.other) {
      const text = str(b[`${q.key}_other`], 200);
      if (text) out.push([`${q.key}_other`, text]);
    }
  }
  return out;
}

export async function saveAnswers(accountId: number, answers: [string, string][], survey = SURVEY) {
  const at = now();
  await env.DB.batch(answers.map(([q, a]) => env.DB.prepare(
    `INSERT INTO answers (account_id, survey, question, answer, at) VALUES (?, ?, ?, ?, ?)
     ON CONFLICT (account_id, survey, question) DO UPDATE SET answer = excluded.answer, at = excluded.at`).bind(accountId, survey, q, a, at)));
}

export const hasAnswered = (accountId: number, survey = SURVEY) =>
  env.DB.prepare('SELECT 1 FROM answers WHERE account_id = ? AND survey = ? LIMIT 1').bind(accountId, survey).first().then(r => !!r);

export const answersFor = (accountId: number) =>
  env.DB.prepare('SELECT survey, question, answer, at FROM answers WHERE account_id = ? ORDER BY survey, at')
    .bind(accountId).all<{ survey: string; question: string; answer: string; at: string }>().then(r => r.results);

/* The panel's Survey page: how many chose each answer, all time or for one month (in India). Typed "other" text
   is listed on its own. */
export async function surveyCounts(month: string, survey = SURVEY) {
  const inMonth = month ? ` AND strftime('%Y-%m', at, '+330 minutes') = ?` : '';
  const bind = month ? [survey, month] : [survey];
  const [counts, others, people, months] = await Promise.all([
    env.DB.prepare(`SELECT question, answer, COUNT(*) AS n FROM answers WHERE survey = ?${inMonth} AND question NOT LIKE '%\\_other' ESCAPE '\\' GROUP BY question, answer`)
      .bind(...bind).all<{ question: string; answer: string; n: number }>().then(r => r.results),
    env.DB.prepare(`SELECT x.answer, x.at, a.uid, a.email FROM answers x JOIN accounts a ON a.id = x.account_id
        WHERE x.survey = ?${inMonth.replace(/\bat\b/g, 'x.at')} AND x.question LIKE '%\\_other' ESCAPE '\\' ORDER BY x.at DESC LIMIT 100`)
      .bind(...bind).all<{ answer: string; at: string; uid: string; email: string }>().then(r => r.results),
    env.DB.prepare(`SELECT COUNT(DISTINCT account_id) AS n FROM answers WHERE survey = ?${inMonth}`).bind(...bind).first<{ n: number }>(),
    env.DB.prepare(`SELECT DISTINCT strftime('%Y-%m', at, '+330 minutes') AS m FROM answers WHERE survey = ? ORDER BY m DESC`).bind(survey)
      .all<{ m: string }>().then(r => r.results.map(x => x.m)),
  ]);
  return { counts, others, people: people!.n, months };
}
