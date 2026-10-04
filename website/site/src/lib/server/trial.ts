/* The free trial: TRIAL.days (consts.ts) on one ARN, with nothing to pay.
   It starts in the app, not on the website. When the app binds an ARN to an account that has never had a plan
   (/api/app/bind), that call starts the trial and takes the slot in one step. Once per account. `trials` is the
   record, not a rule: one row per trial started, kept for good, so how often an ARN comes back under another email
   can be counted (migrations/0010_trial_history.sql has the query).
   A trial is a row in `plans` with source 'trial', so the app, Downloads and the panel treat it as a running plan.
   It differs in two ways: it is bought (or gifted over) like a first plan, the year then running from the trial's
   last day (account.ts yearFrom); and it is emailed about, once before it ends and once after. */
import { env } from 'cloudflare:workers';
import { TRIAL } from '../../consts';
import { trialEndingMail, trialEndedMail } from '../emails';
import { longDate } from '../date';
import { send } from './mail';
import { record } from './errors';
import { event } from './events';
import { now, ago, todayIST, istDay, plusDays, HOUR, siteOrigin } from './util';

/* Starts the trial with this ARN in its slot. One D1 batch: the first statement makes the plan (only for an account
   with none), and each later one acts only if the one before did. Returns the
   trial's last day, or null if it didn't start. */
export async function startTrial(accountId: number, arn: string, holder: string): Promise<string | null> {
  const today = todayIST(), until = plusDays(today, TRIAL.days), at = now();
  try {
    const [plan] = await env.DB.batch([
      env.DB.prepare(`INSERT INTO plans (account_id, slots, starts_on, ends_on, source, updated_at)
          SELECT id, 1, ?2, ?3, 'trial', ?4 FROM accounts WHERE id = ?1
          ON CONFLICT (account_id) DO NOTHING`).bind(accountId, today, until, at),
      env.DB.prepare('INSERT INTO arns (arn, account_id, holder) SELECT ?1, ?2, ?3 WHERE changes() > 0').bind(arn, accountId, holder),
      env.DB.prepare('INSERT INTO trials (arn, email, started_at) SELECT ?1, email, ?3 FROM accounts WHERE id = ?2 AND changes() > 0').bind(arn, accountId, at),
      env.DB.prepare(`INSERT INTO events (at, actor, action, account_id, ref, note)
          SELECT ?1, 'app', 'trial.started', ?2, ?3, ?4 WHERE changes() > 0`).bind(at, accountId, arn, `${holder} · until ${until}`),
    ]);
    return plan.meta.changes ? until : null;
  } catch (e) {
    /* another account took this ARN a moment ago: the batch is undone, and nothing started */
    if (/UNIQUE/i.test(String(e))) return null;
    throw e;
  }
}

/* The hourly job: "your trial ends on …" (from TRIAL.remind days before its last day) and "your trial has ended",
   each once per account. The activity log is what remembers that one went. A mail day starts at 10 in the morning in
   India, so nothing goes out at midnight when the date turns. A trial that was bought is no longer a trial, and gets
   neither. */
export async function sendTrialMails() {
  const day = istDay(ago(10 * HOUR)), link = `${siteOrigin()}/checkout`;
  const due = (action: 'trial.ending' | 'trial.ended', when: string, ...days: string[]) =>
    env.DB.prepare(`SELECT a.id, a.email, p.ends_on FROM plans p JOIN accounts a ON a.id = p.account_id
        WHERE p.source = 'trial' AND a.delete_after IS NULL AND ${when}
          AND NOT EXISTS (SELECT 1 FROM events e WHERE e.account_id = a.id AND e.action = ?1) LIMIT 50`)
      .bind(action, ...days).all<{ id: number; email: string; ends_on: string }>().then(r => r.results);
  const sent = { ending: 0, ended: 0 };
  for (const t of await due('trial.ending', 'p.ends_on BETWEEN ?2 AND ?3', todayIST(), plusDays(day, TRIAL.remind))) {
    try {
      await send(t.email, trialEndingMail({ until: longDate(t.ends_on), link }));
      await event('system', 'trial.ending', t.id, null, `until ${t.ends_on}`).run();
      sent.ending++;
    } catch (e) { await record('email', `trial ending, account ${t.id}`, e); }
  }
  for (const t of await due('trial.ended', 'p.ends_on < ?2', day)) {
    try {
      await send(t.email, trialEndedMail({ link }));
      await event('system', 'trial.ended', t.id, null, `on ${t.ends_on}`).run();
      sent.ended++;
    } catch (e) { await record('email', `trial ended, account ${t.id}`, e); }
  }
  return sent;
}
