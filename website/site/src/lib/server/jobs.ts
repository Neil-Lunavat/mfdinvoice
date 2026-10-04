/* The scheduled jobs (Cron Triggers in wrangler.jsonc; the Worker's scheduled handler is in src/worker.ts).
   Hourly: data copies that are due; the two free-trial emails; the one for a payment left unfinished.
   Daily at 02:00 IST: accounts past delete_after are deleted; old codes, rate-limit hits and expired sessions go.
   A job that fails is written to the Worker's log. By hand: the panel's Overview, or
   locally /__scheduled?cron=… under `wrangler dev --test-scheduled`. */
import { env } from 'cloudflare:workers';
import { sendDueDataCopies } from './support';
import { sendTrialMails } from './trial';
import { nudgeUnfinished } from './upi';
import { record } from './errors';
import { deleteAccount } from './account';
import { now, ago, DAY } from './util';

export const HOURLY = '0 * * * *';
export const DAILY = '30 20 * * *';      /* 20:30 UTC = 02:00 IST */

async function step<T>(name: string, fn: () => Promise<T>): Promise<T | string> {
  try { return await fn(); }
  catch (e) { await record('job', name, e); return 'failed'; }
}

export async function hourly() {
  return {
    data_copies: await step('hourly: data copies', sendDueDataCopies),
    trial_mails: await step('hourly: trial emails', sendTrialMails),
    unfinished: await step('hourly: unfinished payments', nudgeUnfinished),
  };
}

export async function daily() {
  return {
    accounts_deleted: await step('daily: deletions', async () => {
      const due = (await env.DB.prepare('SELECT id, email FROM accounts WHERE delete_after IS NOT NULL AND delete_after <= ?').bind(now())
        .all<{ id: number; email: string }>()).results;
      for (const a of due) await deleteAccount(a.id, a.email, now());
      return due.length;
    }),
    cleared: await step('daily: clean-up', async () => {
      const r = await env.DB.batch([
        env.DB.prepare('DELETE FROM codes WHERE created_at < ?').bind(ago(DAY)),
        env.DB.prepare('DELETE FROM hits WHERE at < ?').bind(ago(DAY)),
        env.DB.prepare('DELETE FROM sessions WHERE expires_at < ?').bind(now()),
      ]);
      return { codes: r[0].meta.changes, hits: r[1].meta.changes, sessions: r[2].meta.changes };
    }),
  };
}

export const run = (cron: string) => (cron === DAILY ? daily() : hourly());
